from __future__ import annotations

from typing import Optional

import numpy as np

from .base_asr import BaseASR

try:
    from funasr import AutoModel
    from funasr.utils.postprocess_utils import rich_transcription_postprocess
    FUNASR_AVAILABLE = True
except Exception:
    FUNASR_AVAILABLE = False
    AutoModel = None


class SenseVoiceASR(BaseASR):
    """SenseVoiceSmall ASR implementation with VAD support.

    Baseline ASR module using FunASR's SenseVoiceSmall model.
    Supports multiple languages (zh, en, yue, ja, ko) with automatic detection.
    """

    def __init__(
        self,
        model_name: str = "iic/SenseVoiceSmall",
        vad_model: str = "fsmn-vad",
        device: str = "cuda",
        vad_max_segment_time: int = 30000,
    ):
        if not FUNASR_AVAILABLE:
            raise ImportError("FunASR not installed. Run: pip install funasr")
        self._model_name = model_name
        self._vad_model = vad_model
        self._device = device
        self._vad_max_segment_time = vad_max_segment_time
        self._model = None
        self._loaded = False

    def load_model(self) -> None:
        if self._loaded:
            return
        self._model = AutoModel(
            model=self._model_name,
            vad_model=self._vad_model,
            vad_kwargs={"max_single_segment_time": self._vad_max_segment_time},
            device=self._device,
        )
        self._loaded = True

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

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str = "auto",
    ) -> str:
        """Transcribe audio to text.

        Args:
            audio: Audio waveform (float32, mono, 16kHz recommended).
            sample_rate: Sample rate of input audio.
            language: Language hint ("zh", "en", "yue", "ja", "ko", "auto").

        Returns:
            Transcribed text with punctuation.
        """
        if not self._loaded:
            self.load_model()

        # FunASR expects audio at 16kHz
        if sample_rate != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)

        # Ensure float32
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)

        res = self._model.generate(
            input=audio,
            language=language,
            use_itn=True,
            batch_size_s=60,
        )

        if res and len(res) > 0:
            raw_text = res[0].get("text", "")
            return rich_transcription_postprocess(raw_text)
        return ""
