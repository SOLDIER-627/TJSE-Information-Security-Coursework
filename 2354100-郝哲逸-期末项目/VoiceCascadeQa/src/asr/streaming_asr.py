from __future__ import annotations

from typing import Optional

import numpy as np

from .base_asr import BaseASR

try:
    from funasr import AutoModel
    FUNASR_AVAILABLE = True
except Exception:
    FUNASR_AVAILABLE = False


class StreamingASR(BaseASR):
    """Streaming ASR using paraformer-zh-streaming.

    Improved ASR module that processes audio in chunks for real-time
    transcription. Uses chunk_size=[0,10,5] for ~600ms chunks.
    """

    def __init__(
        self,
        model_name: str = "paraformer-zh-streaming",
        device: str = "cuda",
        chunk_size: Optional[list[int]] = None,
        encoder_chunk_look_back: int = 4,
        decoder_chunk_look_back: int = 1,
    ):
        if not FUNASR_AVAILABLE:
            raise ImportError("FunASR not installed. Run: pip install funasr")
        self._model_name = model_name
        self._device = device
        self._chunk_size = chunk_size or [0, 10, 5]
        self._encoder_chunk_look_back = encoder_chunk_look_back
        self._decoder_chunk_look_back = decoder_chunk_look_back
        self._model = None
        self._loaded = False
        self._cache = {}

    def load_model(self) -> None:
        if self._loaded:
            return
        self._model = AutoModel(model=self._model_name, device=self._device)
        self._loaded = True

    def unload_model(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        self._loaded = False
        self._cache = {}

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def chunk_stride(self) -> int:
        """Number of samples per chunk stride (chunk_size[1] * 960)."""
        return self._chunk_size[1] * 960

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str = "zh",
    ) -> str:
        """Full transcription using streaming model (all chunks at once).

        For real streaming usage, use process_chunk() instead.
        """
        if not self._loaded:
            self.load_model()

        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        self._cache = {}
        stride = self.chunk_stride
        total_chunks = int(len(audio) - 1) // stride + 1
        pieces: list[str] = []

        for i in range(total_chunks):
            chunk = audio[i * stride : (i + 1) * stride]
            is_final = i == total_chunks - 1
            res = self._model.generate(
                input=chunk,
                cache=self._cache,
                is_final=is_final,
                chunk_size=self._chunk_size,
                encoder_chunk_look_back=self._encoder_chunk_look_back,
                decoder_chunk_look_back=self._decoder_chunk_look_back,
            )
            if res and len(res) > 0:
                text = res[0].get("text", "")
                if text:
                    pieces.append(text)

        return "".join(pieces)

    def reset_stream(self) -> None:
        """Reset streaming cache for a new utterance."""
        self._cache = {}

    def process_chunk(
        self,
        audio_chunk: np.ndarray,
        is_final: bool = False,
    ) -> str:
        """Process a single audio chunk and return partial transcription.

        Args:
            audio_chunk: Audio chunk of chunk_stride samples.
            is_final: Whether this is the last chunk.

        Returns:
            Partial transcription text.
        """
        if not self._loaded:
            self.load_model()

        if audio_chunk.dtype != np.float32:
            audio_chunk = audio_chunk.astype(np.float32)

        res = self._model.generate(
            input=audio_chunk,
            cache=self._cache,
            is_final=is_final,
            chunk_size=self._chunk_size,
            encoder_chunk_look_back=self._encoder_chunk_look_back,
            decoder_chunk_look_back=self._decoder_chunk_look_back,
        )

        if res and len(res) > 0:
            text = res[0].get("text", "")
            if text:
                return text
        return ""
