from __future__ import annotations

from typing import Generator, Optional

import numpy as np

from .base_tts import BaseTTS

KOKORO_AVAILABLE = False
_KPipeline = None

try:
    from kokoro import KPipeline as _KPipeline
    KOKORO_AVAILABLE = True
except ImportError:
    pass

# edge-tts fallback
EDGE_TTS_AVAILABLE = False
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    pass


class KokoroTTS(BaseTTS):
    """Kokoro-82M TTS with streaming support.

    Falls back to edge-tts if Kokoro is not available.
    Uses CPU by default for low-latency local inference.
    """

    SAMPLE_RATE = 24000
    DEFAULT_VOICE = "zf_xiaobei"
    # Split on Chinese/English sentence endings for streaming
    STREAM_SPLIT_PATTERN = r'[。！？；.!?\n]+'

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        speed: float = 1.0,
        device: str = "cpu",
        lang_code: str = "z",
        fallback: str = "edge-tts",
        edge_voice: str = "zh-CN-XiaoxiaoNeural",
    ):
        self._voice = voice
        self._speed = speed
        self._device = device
        self._lang_code = lang_code
        self._fallback = fallback
        self._edge_voice = edge_voice
        self._pipeline = None
        self._loaded = False
        self._use_fallback = False

    def load_model(self) -> None:
        if self._loaded:
            return

        import os
        # Use HF mirror if no endpoint set and direct access fails
        if not os.environ.get("HF_ENDPOINT"):
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

        if KOKORO_AVAILABLE:
            try:
                self._pipeline = _KPipeline(lang_code=self._lang_code, device=self._device)
                self._loaded = True
                self._use_fallback = False
                print(f"[TTS] Kokoro-82M loaded (voice: {self._voice}, device: {self._device})")
                return
            except Exception as e:
                print(f"[TTS] Kokoro load failed: {e}, falling back to {self._fallback}")

        if EDGE_TTS_AVAILABLE:
            self._use_fallback = True
            self._loaded = True
            print(f"[TTS] Using edge-tts fallback (voice: {self._edge_voice})")
        else:
            raise ImportError("Neither Kokoro nor edge-tts available")

    def unload_model(self) -> None:
        if self._pipeline is not None:
            del self._pipeline
            self._pipeline = None
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def sample_rate(self) -> int:
        return self.SAMPLE_RATE

    def synthesize(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> tuple[np.ndarray, int]:
        """Synthesize speech from text (non-streaming, returns full audio)."""
        if not self._loaded:
            self.load_model()

        voice = speaker_id or self._voice

        if self._use_fallback:
            from .cosyvoice_tts import _edge_tts_synthesize
            return _edge_tts_synthesize(text, self._edge_voice)

        chunks = []
        for _, _, audio in self._pipeline(text, voice=voice, speed=self._speed):
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            chunks.append(audio)

        if chunks:
            return np.concatenate(chunks).astype(np.float32), self.SAMPLE_RATE
        return np.array([], dtype=np.float32), self.SAMPLE_RATE

    def synthesize_stream(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> Generator[tuple[np.ndarray, int], None, None]:
        """Synthesize speech in streaming chunks (sentence-level)."""
        if not self._loaded:
            self.load_model()

        voice = speaker_id or self._voice

        if self._use_fallback:
            # edge-tts doesn't support streaming, yield full audio
            from .cosyvoice_tts import _edge_tts_synthesize
            audio, sr = _edge_tts_synthesize(text, self._edge_voice)
            yield audio, sr
            return

        for _, _, audio in self._pipeline(
            text, voice=voice, speed=self._speed,
            split_pattern=self.STREAM_SPLIT_PATTERN,
        ):
            if hasattr(audio, "cpu"):
                audio = audio.cpu().numpy()
            yield audio.astype(np.float32), self.SAMPLE_RATE