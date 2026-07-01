from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..asr.sensevoice_asr import SenseVoiceASR
from ..asr.streaming_asr import StreamingASR
from ..llm.openai_llm import OpenAILLM
from ..safety.safety_gate import SafetyGate, SafetyResult
from ..tts.kokoro_tts import KokoroTTS
from ..tts.streaming_tts import StreamingTTS, normalize_tts_text
from ..scheduling.transition_phrases import TransitionPhrases
from ..utils.timer import Timer
from ..utils.config_loader import load_config


@dataclass
class ImprovedPipelineResult:
    text_input: str
    text_output: str
    audio_output: list[tuple[np.ndarray, int]]
    safety_result: str
    timer: Timer
    transition_used: bool


class ImprovedPipeline:
    """Streaming parallel pipeline with all four improvements.

    Improvements over baseline:
    1. Streaming parallel: streaming ASR, LLM, TTS with async processing
    2. Transition phrases: pre-synthesized filler audio after VAD endpoint
    3. Hotwords: streaming ASR with hotword biasing for shipbuilding terms
    4. Safety gate: keyword-based short-circuit before LLM
    """

    _SENTENCE_ENDINGS = ("。", "！", "？", "；", ".", "!", "?", ";")

    def __init__(self, config: Optional[dict] = None, enable_playback: bool = True):
        self._config = config or load_config()
        self._timer = Timer()
        self._enable_playback = enable_playback

        self._asr: Optional[SenseVoiceASR] = None
        self._streaming_asr: Optional[StreamingASR] = None
        self._llm: Optional[OpenAILLM] = None
        self._tts: Optional[CosyVoiceTTS] = None
        self._streaming_tts: Optional[StreamingTTS] = None
        self._safety: Optional[SafetyGate] = None
        self._transition: Optional[TransitionPhrases] = None
        self._player = None  # Lazy: only created when needed
        self._hotwords: list[str] = []

    def _ensure_modules(self) -> None:
        if self._asr is not None:
            return

        cfg = self._config

        # Baseline ASR for fallback
        self._asr = SenseVoiceASR(
            model_name=cfg["asr"]["baseline_model"],
            vad_model=cfg["asr"]["vad_model"],
            device=cfg["device"],
        )
        self._asr.load_model()

        # Streaming ASR
        self._streaming_asr = StreamingASR(
            model_name=cfg["asr"]["streaming_model"],
            device=cfg["device"],
        )
        self._streaming_asr.load_model()

        # LLM
        self._llm = OpenAILLM(
            api_base=cfg["llm"]["api_base"],
            api_key=cfg["llm"]["api_key"],
            model=cfg["llm"]["model"],
            default_system_prompt=cfg["llm"]["system_prompt"],
            max_tokens=cfg["llm"]["max_tokens"],
            temperature=cfg["llm"]["temperature"],
        )

        # TTS
        tts_engine = cfg["tts"].get("engine", "kokoro")
        if tts_engine == "kokoro":
            kokoro_cfg = cfg["tts"].get("kokoro", {})
            self._tts = KokoroTTS(
                voice=kokoro_cfg.get("voice", "zf_xiaobei"),
                speed=kokoro_cfg.get("speed", 1),
                device=kokoro_cfg.get("device", "cpu"),
                fallback=cfg["tts"].get("fallback", "edge-tts"),
                edge_voice=cfg["tts"].get("edge_voice", "zh-CN-XiaoxiaoNeural"),
            )
        else:
            from ..tts.cosyvoice_tts import CosyVoiceTTS
            self._tts = CosyVoiceTTS(
                model_dir=cfg["tts"]["model_dir"],
                speaker_id=cfg["tts"]["speaker_id"],
                device=cfg["device"],
                fallback=cfg["tts"].get("fallback", "edge-tts"),
                edge_voice=cfg["tts"].get("edge_voice", "zh-CN-XiaoxiaoNeural"),
            )
        self._tts.load_model()

        # Streaming TTS wrapper
        self._streaming_tts = StreamingTTS(self._tts, normalize=True)

        # Safety gate
        if cfg.get("safety", {}).get("enabled", True):
            self._safety = SafetyGate(
                keywords_file=cfg["safety"]["keywords_file"],
            )
        else:
            self._safety = None

        # Transition phrases
        self._transition = TransitionPhrases(
            tts=self._tts,
            phrases=cfg["transition"]["phrases"],
            crossfade_ms=cfg["transition"]["crossfade_ms"],
        )
        self._transition.pre_synthesize()

        # Load hotwords
        self._load_hotwords(cfg["asr"]["hotword_file"])

        # Player is NOT created here — lazy init via _ensure_player()

    def _ensure_player(self):
        """Lazily create AudioPlayer only when playback is needed."""
        if self._player is None:
            try:
                from ..audio.recorder import AudioPlayer
                self._player = AudioPlayer(sample_rate=self._config["tts"]["sample_rate"])
            except ImportError:
                self._player = None
                print("[Player] sounddevice not available, audio playback disabled")

    def _load_hotwords(self, filepath: str) -> None:
        from pathlib import Path
        path = Path(filepath)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                self._hotwords = [line.strip() for line in f if line.strip()]
            print(f"[ASR] Loaded {len(self._hotwords)} hotwords")
        else:
            print(f"[ASR] Hotwords file not found: {filepath}")

    def _do_safety_check(self, text: str) -> tuple[Optional[SafetyResult], str, str]:
        """Run safety check. Returns (result_enum_or_None, result_value_str, reason)."""
        if self._safety is None:
            return None, "safe", ""
        check = self._safety.check(text)
        return check.result, check.result.value, check.reason

    def _apply_hotwords(self, text: str) -> str:
        """Correct likely ASR errors using domain hotwords.

        Only replaces a segment when:
        - It has the same length as a hotword
        - Edit distance is exactly 1
        - The segment shares at least 50% of characters with the hotword
          (this prevents "船体" being "corrected" to "船坞" — they share
          only 1 of 2 chars, which is a different word, not an ASR typo)
        - The segment is NOT already a hotword itself
        """
        if not self._hotwords or not text:
            return text

        hotword_set = set(self._hotwords)
        result = text

        for hw in self._hotwords:
            if len(hw) < 3 or len(hw) > 4:
                continue
            for i in range(len(result) - len(hw) + 1):
                segment = result[i:i + len(hw)]
                if segment == hw or segment in hotword_set:
                    continue
                if self._edit_distance(segment, hw) == 1:
                    # Only correct if most chars match (likely a near-homophone typo)
                    shared = sum(1 for a, b in zip(segment, hw) if a == b)
                    if shared >= len(hw) / 2:
                        print(f"[Hotword] Corrected: '{segment}' -> '{hw}'")
                        result = result[:i] + hw + result[i + len(hw):]
                        break
        return result

    @staticmethod
    def _edit_distance(s1: str, s2: str) -> int:
        """Compute Levenshtein edit distance between two strings."""
        if len(s1) < len(s2):
            return ImprovedPipeline._edit_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)
        prev = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            curr = [i + 1]
            for j, c2 in enumerate(s2):
                curr.append(min(
                    prev[j + 1] + 1,
                    curr[j] + 1,
                    prev[j] + (0 if c1 == c2 else 1),
                ))
            prev = curr
        return prev[-1]

    def _run_streaming_asr(self, audio: np.ndarray, sample_rate: int) -> str:
        """Run streaming ASR on audio, return final transcription."""
        self._streaming_asr.reset_stream()

        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
            sample_rate = 16000

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        stride = self._streaming_asr.chunk_stride
        total_chunks = max(1, int(len(audio) - 1) // stride + 1)
        pieces: list[str] = []

        for i in range(total_chunks):
            chunk = audio[i * stride : (i + 1) * stride]
            is_final = i == total_chunks - 1
            partial = self._streaming_asr.process_chunk(chunk, is_final=is_final)
            if partial:
                pieces.append(partial)

        final_text = "".join(pieces).strip()
        print(f"[ASR] streaming result: {final_text}")
        final_text = self._apply_hotwords(final_text)
        return final_text

    def run_from_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> ImprovedPipelineResult:
        """Run improved pipeline from audio input."""
        self._ensure_modules()
        timer = self._timer.start()
        timer.mark("t_user_silent", "User stopped speaking")

        # Stage 1: Streaming ASR
        text_input = self._run_streaming_asr(audio, sample_rate)

        # Fallback to baseline ASR only when streaming produced nothing.
        # Previous "always-run-baseline" approach added ~20s overhead per run
        # for marginal quality gain — LLM can handle minor ASR errors via
        # system prompt rule #6 (homophone inference).
        if not text_input.strip():
            baseline_text = self._asr.transcribe(audio, sample_rate=sample_rate,
                                                  language=self._config["asr"]["language"])
            if baseline_text.strip():
                print(f"[ASR] streaming result empty, fallback to SenseVoice: '{text_input}' -> '{baseline_text}'")
                text_input = baseline_text

        timer.mark("t_asr_complete", "ASR transcription complete")

        # Stage 2: Safety check
        safety_result, safety_value, safety_reason = self._do_safety_check(text_input)

        if safety_result is not None and safety_result != SafetyResult.SAFE:
            safety_msg = f"[安全提示] {safety_reason}"
            timer.mark("t_safety_check", "Safety check - blocked")
            audio_out, sr = self._tts.synthesize(safety_msg)
            timer.mark("t_tts_first_chunk", "TTS safety message synthesized")
            timer.mark("t_first_playable", "Safety audio ready for playback")
            timer.finish()

            return ImprovedPipelineResult(
                text_input=text_input,
                text_output=safety_msg,
                audio_output=[(audio_out, sr)],
                safety_result=safety_value,
                timer=timer,
                transition_used=False,
            )

        timer.mark("t_safety_check", "Safety check - safe")

        # Stage 3-4: Streaming LLM → Sentence-level TTS
        result = asyncio.run(self._streaming_llm_tts(text_input, timer))
        return result

    async def _streaming_llm_tts(
        self,
        text_input: str,
        timer: Timer,
    ) -> ImprovedPipelineResult:
        """Stream LLM output and synthesize TTS sentence by sentence.

        Transition phrase:
        - If playback is enabled AND player is available, enqueue transition
          immediately for low perceived latency, then mark t_first_playable.
        - If no player, don't mark t_first_playable from transition — wait for
          first content audio instead, so latency metrics stay meaningful.
        - t_first_content always marks when actual answer audio is ready.

        Text is accumulated from the same stream — no duplicate LLM call.
        """
        can_play = self._enable_playback
        if can_play:
            self._ensure_player()
            can_play = self._player is not None

        transition_audio = self._transition.get_random_phrase()
        transition_used = False
        first_playable_marked = False

        if transition_audio is not None and can_play:
            self._player.start()
            self._player.enqueue(transition_audio[0], transition_audio[1])
            transition_used = True
            timer.mark("t_first_playable", "Transition phrase enqueued for playback")
            first_playable_marked = True

        audio_chunks: list[tuple[np.ndarray, int]] = []
        first_sentence = True
        full_text = ""
        buffer = ""

        async for chunk in self._llm.generate_stream(text_input):
            full_text += chunk
            buffer += chunk

            while True:
                idx = -1
                for ending in self._SENTENCE_ENDINGS:
                    pos = buffer.find(ending)
                    if pos != -1 and (idx == -1 or pos < idx):
                        idx = pos

                if idx != -1:
                    sentence = buffer[:idx + 1].strip()
                    buffer = buffer[idx + 1:]

                    if sentence and len(sentence) >= 2:
                        if first_sentence:
                            timer.mark("t_llm_first_sentence", "LLM first sentence complete")

                        sentence_norm = normalize_tts_text(sentence)

                        # Streaming TTS: yield audio chunks as they're generated
                        for audio, sr in self._tts.synthesize_stream(sentence_norm):
                            if first_sentence:
                                timer.mark("t_tts_first_chunk", "TTS first chunk ready")
                                timer.mark("t_first_content", "First content audio ready")
                                first_sentence = False

                                if not first_playable_marked:
                                    timer.mark("t_first_playable", "First content audio ready (no transition)")
                                    first_playable_marked = True

                            audio_chunks.append((audio, sr))
                            if can_play:
                                self._player.enqueue(audio, sr)
                else:
                    break

        # Process remaining buffer
        remaining = buffer.strip()
        if remaining and len(remaining) >= 2:
            if first_sentence:
                timer.mark("t_llm_first_sentence", "LLM first sentence (no punctuation)")
                first_sentence = False

            sentence_norm = normalize_tts_text(remaining)
            for audio, sr in self._tts.synthesize_stream(sentence_norm):
                if not any(cp.name == "t_tts_first_chunk" for cp in timer.all_checkpoints()):
                    timer.mark("t_tts_first_chunk", "TTS first chunk ready")
                    timer.mark("t_first_content", "First content audio ready")

                    if not first_playable_marked:
                        timer.mark("t_first_playable", "First content audio ready (no transition)")
                        first_playable_marked = True

                audio_chunks.append((audio, sr))
                if can_play:
                    self._player.enqueue(audio, sr)

        # Edge case: no output at all
        if first_sentence:
            timer.mark("t_llm_first_sentence", "LLM produced no output")
            timer.mark("t_tts_first_chunk", "No TTS output")
            timer.mark("t_first_content", "No content audio")
            if not first_playable_marked:
                timer.mark("t_first_playable", "No playback")

        timer.finish()

        return ImprovedPipelineResult(
            text_input=text_input,
            text_output=full_text,
            audio_output=audio_chunks,
            safety_result="safe",
            timer=timer,
            transition_used=transition_used,
        )

    def run_from_text(self, text: str) -> ImprovedPipelineResult:
        """Run pipeline from text input (skip ASR stage)."""
        self._ensure_modules()
        timer = self._timer.start()

        timer.mark("t_user_silent", "Text input received")
        timer.mark("t_asr_complete", "ASR skipped (text input)")

        safety_result, safety_value, safety_reason = self._do_safety_check(text)

        if safety_result is not None and safety_result != SafetyResult.SAFE:
            safety_msg = f"[安全提示] {safety_reason}"
            timer.mark("t_safety_check", "Safety check - blocked")
            audio_out, sr = self._tts.synthesize(safety_msg)
            timer.mark("t_tts_first_chunk", "TTS safety message synthesized")
            timer.mark("t_first_playable", "Safety audio ready for playback")
            timer.finish()

            return ImprovedPipelineResult(
                text_input=text,
                text_output=safety_msg,
                audio_output=[(audio_out, sr)],
                safety_result=safety_value,
                timer=timer,
                transition_used=False,
            )

        timer.mark("t_safety_check", "Safety check - safe")

        result = asyncio.run(self._streaming_llm_tts(text, timer))
        return result

    def run_interactive(self) -> None:
        """Run interactive mode with streaming improvements."""
        self._ensure_modules()
        self._ensure_player()

        from ..audio.recorder import AudioRecorder
        recorder = AudioRecorder(sample_rate=self._config["audio"]["sample_rate"])

        print("\n=== 改进语音问答系统（流式并行） ===")
        print("按 Enter 开始录音，说完后自动检测静音结束...")
        print("输入 'quit' 退出\n")

        while True:
            cmd = input("按 Enter 开始录音 > ").strip()
            if cmd.lower() == "quit":
                break

            print("录音中...")
            recording = recorder.record_until_silence()
            print(f"录音完成 ({recording.duration_ms:.0f}ms)")

            result = self.run_from_audio(recording.audio, recording.sample_rate)

            print(f"\n识别: {result.text_input}")
            print(f"安全: {result.safety_result}")
            print(f"回答: {result.text_output}")
            print(f"衔接语: {'是' if result.transition_used else '否'}")
            print(f"延迟: {result.timer.summary()}\n")

            if self._player is not None:
                self._player.wait_complete()

    def cleanup(self) -> None:
        if self._asr:
            self._asr.unload_model()
        if self._streaming_asr:
            self._streaming_asr.unload_model()
        if self._tts:
            self._tts.unload_model()
