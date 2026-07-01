from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np


class BaseASR(ABC):
    """Abstract interface for ASR (Automatic Speech Recognition) modules."""

    @abstractmethod
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str = "auto",
    ) -> str:
        """Transcribe audio array to text.

        Args:
            audio: Audio waveform as numpy array (float32, mono).
            sample_rate: Sample rate of the audio.
            language: Language hint ("zh", "en", "auto").

        Returns:
            Transcribed text string.
        """
        ...

    @abstractmethod
    def load_model(self) -> None:
        """Load ASR model into memory/GPU."""
        ...

    @abstractmethod
    def unload_model(self) -> None:
        """Release model from memory/GPU."""
        ...

    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Whether the model is currently loaded."""
        ...
