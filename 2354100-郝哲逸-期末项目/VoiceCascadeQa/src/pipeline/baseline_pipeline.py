from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..asr.sensevoice_asr import SenseVoiceASR
from ..llm.openai_llm import OpenAILLM
from ..safety.safety_gate import SafetyGate, SafetyResult
from ..tts.kokoro_tts import KokoroTTS
from ..utils.timer import Timer
from ..utils.config_loader import load_config


@dataclass
class PipelineResult:
    text_input: str
    text_output: str
    audio_output: Optional[tuple[np.ndarray, int]]
    safety_result: str
    timer: Timer


class BaselinePipeline:
    """Serial baseline pipeline: ASR → Safety → LLM → TTS → Playback.

    All stages run sequentially with no streaming or parallelism.
    """

    def __init__(self, config: Optional[dict] = None):
        self._config = config or load_config()
        self._timer = Timer()

        self._asr: Optional[SenseVoiceASR] = None
        self._llm: Optional[OpenAILLM] = None
        self._tts: Optional[CosyVoiceTTS] = None
        self._safety: Optional[SafetyGate] = None
        self._player = None  # Lazy: only created when needed

    def _ensure_modules(self) -> None:
        if self._asr is None:
            cfg = self._config
            self._asr = SenseVoiceASR(
                model_name=cfg["asr"]["baseline_model"],
                vad_model=cfg["asr"]["vad_model"],
                device=cfg["device"],
            )
            self._asr.load_model()

        if self._llm is None:
            cfg = self._config
            self._llm = OpenAILLM(
                api_base=cfg["llm"]["api_base"],
                api_key=cfg["llm"]["api_key"],
                model=cfg["llm"]["model"],
                default_system_prompt=cfg["llm"]["system_prompt"],
                max_tokens=cfg["llm"]["max_tokens"],
                temperature=cfg["llm"]["temperature"],
            )

        if self._tts is None:
            cfg = self._config
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

        if self._safety is None:
            cfg = self._config
            if cfg.get("safety", {}).get("enabled", True):
                self._safety = SafetyGate(
                    keywords_file=cfg["safety"]["keywords_file"],
                )

    def _ensure_player(self):
        """Lazily create AudioPlayer only when playback is needed."""
        if self._player is None:
            try:
                from ..audio.recorder import AudioPlayer
                self._player = AudioPlayer(sample_rate=self._config["tts"]["sample_rate"])
            except ImportError:
                self._player = None
                print("[Player] sounddevice not available, audio playback disabled")

    def run_from_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> PipelineResult:
        """Run baseline pipeline from audio input."""
        self._ensure_modules()
        timer = self._timer.start()

        # Stage 1: ASR (full transcription)
        timer.mark("t_user_silent", "User stopped speaking")
        text_input = self._asr.transcribe(audio, sample_rate=sample_rate,
                                            language=self._config["asr"]["language"])
        timer.mark("t_asr_complete", "ASR transcription complete")

        # Stage 2: Safety check
        if self._safety is not None:
            safety_check = self._safety.check(text_input)
            timer.mark("t_safety_check", "Safety check complete")

            if safety_check.result != SafetyResult.SAFE:
                safety_msg = f"[安全提示] {safety_check.reason}"
                timer.mark("t_llm_first_sentence", "LLM skipped (safety gate)")
                audio_out, sr = self._tts.synthesize(safety_msg)
                timer.mark("t_tts_first_chunk", "TTS safety message synthesized")
                timer.mark("t_first_playable", "Safety audio ready for playback")
                timer.finish()

                return PipelineResult(
                    text_input=text_input,
                    text_output=safety_msg,
                    audio_output=(audio_out, sr),
                    safety_result=safety_check.result.value,
                    timer=timer,
                )
        else:
            safety_check = None
            timer.mark("t_safety_check", "Safety check skipped (disabled)")

        # Stage 3: LLM (full generation)
        text_output = self._llm.generate(text_input)
        timer.mark("t_llm_first_sentence", "LLM generation complete")

        # Stage 4: TTS (full synthesis)
        audio_out, sr = self._tts.synthesize(text_output)
        timer.mark("t_tts_first_chunk", "TTS synthesis complete")

        # Stage 5: Audio ready
        timer.mark("t_first_playable", "Audio ready for playback")
        timer.finish()

        return PipelineResult(
            text_input=text_input,
            text_output=text_output,
            audio_output=(audio_out, sr),
            safety_result=safety_check.result.value if safety_check else "skipped",
            timer=timer,
        )

    def run_from_text(self, text: str) -> PipelineResult:
        """Run pipeline from text input (skip ASR stage)."""
        self._ensure_modules()
        timer = self._timer.start()

        timer.mark("t_user_silent", "Text input received")
        text_input = text
        timer.mark("t_asr_complete", "ASR skipped (text input)")

        if self._safety is not None:
            safety_check = self._safety.check(text_input)
            timer.mark("t_safety_check", "Safety check complete")

            if safety_check.result != SafetyResult.SAFE:
                safety_msg = f"[安全提示] {safety_check.reason}"
                timer.mark("t_llm_first_sentence", "LLM skipped (safety gate)")
                audio_out, sr = self._tts.synthesize(safety_msg)
                timer.mark("t_tts_first_chunk", "TTS safety message synthesized")
                timer.mark("t_first_playable", "Safety audio ready for playback")
                timer.finish()

                return PipelineResult(
                    text_input=text_input,
                    text_output=safety_msg,
                    audio_output=(audio_out, sr),
                    safety_result=safety_check.result.value,
                    timer=timer,
                )
        else:
            safety_check = None
            timer.mark("t_safety_check", "Safety check skipped (disabled)")

        text_output = self._llm.generate(text_input)
        timer.mark("t_llm_first_sentence", "LLM generation complete")

        audio_out, sr = self._tts.synthesize(text_output)
        timer.mark("t_tts_first_chunk", "TTS synthesis complete")
        timer.mark("t_first_playable", "Audio ready for playback")
        timer.finish()

        return PipelineResult(
            text_input=text_input,
            text_output=text_output,
            audio_output=(audio_out, sr),
            safety_result=safety_check.result.value if safety_check else "skipped",
            timer=timer,
        )

    def run_interactive(self) -> None:
        """Run interactive mode: record from microphone, process, play back."""
        self._ensure_modules()
        self._ensure_player()

        from ..audio.recorder import AudioRecorder
        recorder = AudioRecorder(sample_rate=self._config["audio"]["sample_rate"])

        print("\n=== 基线语音问答系统 ===")
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
            print(f"延迟: {result.timer.summary()}\n")

            # Play audio
            if result.audio_output and self._player is not None:
                audio, sr = result.audio_output
                self._player.enqueue(audio, sr)
                self._player.start()
                self._player.wait_complete()

    def cleanup(self) -> None:
        if self._asr:
            self._asr.unload_model()
        if self._tts:
            self._tts.unload_model()
