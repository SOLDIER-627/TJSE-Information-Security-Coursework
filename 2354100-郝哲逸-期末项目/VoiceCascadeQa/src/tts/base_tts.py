from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generator, Optional

import numpy as np


class BaseTTS(ABC):
    """Abstract interface for TTS (Text-to-Speech) modules."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> tuple[np.ndarray, int]:
        """Synthesize speech from text (non-streaming).

        Args:
            text: Text to synthesize.
            speaker_id: Speaker identity (model-specific).

        Returns:
            Tuple of (audio_array, sample_rate).
        """
        ...

    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        speaker_id: Optional[str] = None,
    ) -> Generator[tuple[np.ndarray, int], None, None]:
        """Synthesize speech in streaming chunks.

        Yields:
            Tuple of (audio_chunk, sample_rate) for each chunk.
        """
        ...

    @abstractmethod
    def load_model(self) -> None:
        """Load TTS model into memory/GPU."""
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
