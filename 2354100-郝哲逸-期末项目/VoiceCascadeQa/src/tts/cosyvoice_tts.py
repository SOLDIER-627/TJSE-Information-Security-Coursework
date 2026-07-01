from __future__ import annotations

from typing import Generator, Optional

import numpy as np

from .base_tts import BaseTTS

# CosyVoice availability flag
COSYVOICE_AVAILABLE = False
_CosyVoiceModel = None

try:
    from cosyvoice.cli.cosyvoice import CosyVoice as _CosyVoiceModel
    COSYVOICE_AVAILABLE = True
except ImportError:
    pass

# edge-tts fallback
EDGE_TTS_AVAILABLE = False
try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    pass


def _edge_tts_synthesize(text: str, voice: str = "zh-CN-XiaoxiaoNeural",
                          rate: str = "+0%", volume: str = "+0%") -> tuple[np.ndarray, int]:
    """Synthesize using edge-tts (Microsoft free TTS API).

    Safe to call from any context — runs edge-tts in a dedicated thread
    to avoid asyncio event-loop nesting issues.
    """
    import io

    async def _run():
        communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
        buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                buffer.write(chunk["data"])
        buffer.seek(0)
        return buffer

    import concurrent.futures

    def _run_in_thread():
        import asyncio
        return asyncio.run(_run())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        buffer = pool.submit(_run_in_thread).result()

    import soundfile as sf
    audio, sr = sf.read(buffer)
    return audio.astype(np.float32), sr


class CosyVoiceTTS(BaseTTS):
    """CosyVoice-300M TTS implementation with streaming support.

    Falls back to edge-tts if CosyVoice is not available.
    """

    def __init__(
        self,
        model_dir: str = "",
        speaker_id: str = "中文女",
        device: str = "cuda",
        fallback: str = "edge-tts",
        edge_voice: str = "zh-CN-XiaoxiaoNeural",
    ):
        self._model_dir = model_dir
        self._speaker_id = speaker_id
        self._device = device
        self._fallback = fallback
        self._edge_voice = edge_voice
        self._model = None
        self._loaded = False
        self._use_fallback = False

    def load_model(self) -> None:
        if self._loaded:
            return

        if COSYVOICE_AVAILABLE and self._model_dir:
            try:
                self._model = _CosyVoiceModel(self._model_dir)
                self._loaded = True
                self._use_fallback = False
                return
            except Exception as e:
                print(f"[TTS] CosyVoice load failed: {e}, falling back to {self._fallback}")

        # Fallback to edge-tts
        if EDGE_TTS_AVAILABLE:
            self._use_fallback = True
            self._loaded = True
            print(f"[TTS] Using edge-tts fallback (voice: {self._edge_voice})")
        else:
            raise ImportError("Neither CosyVoice nor edge-tts available")

    def unload_model(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def sample_rate(self) -> int:
        if self._use_fallback:
            return 24000
        if self._model is not None:
            return self._model.sample_rate
        return 22050

    def synthesize(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> tuple[np.ndarray, int]:
        """Synthesize speech from text (non-streaming)."""
        if not self._loaded:
            self.load_model()

        spk = speaker_id or self._speaker_id

        if self._use_fallback:
            return _edge_tts_synthesize(text, self._edge_voice)

        # CosyVoice non-streaming
        audio_chunks = []
        for result in self._model.inference_sft(text, spk, stream=False):
            speech = result["tts_speech"]
            # Convert torch tensor to numpy
            if hasattr(speech, "cpu"):
                speech = speech.cpu().numpy()
            audio_chunks.append(speech.squeeze())

        if audio_chunks:
            audio = np.concatenate(audio_chunks)
            return audio, self.sample_rate
        return np.array([], dtype=np.float32), self.sample_rate

    def synthesize_stream(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> Generator[tuple[np.ndarray, int], None, None]:
        """Synthesize speech in streaming chunks (sentence-level)."""
        if not self._loaded:
            self.load_model()

        spk = speaker_id or self._speaker_id

        if self._use_fallback:
            # edge-tts doesn't support true streaming, yield full audio
            audio, sr = _edge_tts_synthesize(text, self._edge_voice)
            yield audio, sr
            return

        # CosyVoice streaming
        for result in self._model.inference_sft(text, spk, stream=True):
            speech = result["tts_speech"]
            if hasattr(speech, "cpu"):
                speech = speech.cpu().numpy()
            yield speech.squeeze(), self.sample_rate
