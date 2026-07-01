from __future__ import annotations

import numpy as np
from typing import Optional

from ..tts.cosyvoice_tts import CosyVoiceTTS


# Default transition phrases
DEFAULT_PHRASES = [
    "让我为您查找相关信息",
    "正在为您解答",
    "请稍等，我来查找",
]


class TransitionPhrases:
    """Transition phrase pre-synthesis and insertion.

    Pre-synthesizes short filler phrases at startup to be played
    immediately after VAD endpoint detection, reducing perceived latency.
    Uses crossfade when transitioning to main content audio.
    """

    def __init__(
        self,
        tts: CosyVoiceTTS,
        phrases: Optional[list[str]] = None,
        crossfade_ms: int = 50,
    ):
        self._tts = tts
        self._phrases = phrases or DEFAULT_PHRASES
        self._crossfade_ms = crossfade_ms
        self._cached_audio: list[tuple[np.ndarray, int]] = []
        self._ready = False

    def pre_synthesize(self) -> None:
        """Pre-synthesize all transition phrases at startup."""
        self._cached_audio.clear()
        for phrase in self._phrases:
            audio, sr = self._tts.synthesize(phrase)
            self._cached_audio.append((audio, sr))
        self._ready = True
        print(f"[Transition] Pre-synthesized {len(self._cached_audio)} phrases")

    def get_random_phrase(self) -> Optional[tuple[np.ndarray, int]]:
        """Get a random pre-synthesized transition phrase."""
        if not self._ready or not self._cached_audio:
            return None
        import random
        return random.choice(self._cached_audio)

    def get_phrase(self, index: int = 0) -> Optional[tuple[np.ndarray, int]]:
        """Get a specific pre-synthesized transition phrase by index."""
        if not self._ready or index >= len(self._cached_audio):
            return None
        return self._cached_audio[index]

    @staticmethod
    def crossfade(
        audio_a: np.ndarray,
        audio_b: np.ndarray,
        crossfade_samples: int,
    ) -> np.ndarray:
        """Apply crossfade between two audio segments.

        Args:
            audio_a: First audio segment (ending).
            audio_b: Second audio segment (beginning).
            crossfade_samples: Number of samples for crossfade.

        Returns:
            Combined audio with crossfade transition.
        """
        if len(audio_a) < crossfade_samples or len(audio_b) < crossfade_samples:
            crossfade_samples = min(len(audio_a), len(audio_b))

        if crossfade_samples <= 0:
            return np.concatenate([audio_a, audio_b])

        fade_out = np.linspace(1.0, 0.0, crossfade_samples, dtype=np.float32)
        fade_in = np.linspace(0.0, 1.0, crossfade_samples, dtype=np.float32)

        # Apply fades
        tail_a = audio_a[-crossfade_samples:] * fade_out
        head_b = audio_b[:crossfade_samples] * fade_in

        result = np.concatenate([
            audio_a[:-crossfade_samples],
            tail_a + head_b,
            audio_b[crossfade_samples:],
        ])
        return result

    def blend_with_content(
        self,
        transition_audio: np.ndarray,
        content_audio: np.ndarray,
        sample_rate: int,
    ) -> np.ndarray:
        """Blend transition phrase with content audio using crossfade.

        If transition is still playing when content arrives, crossfade.
        Otherwise, just concatenate.
        """
        crossfade_samples = int(self._crossfade_ms * sample_rate / 1000)
        return self.crossfade(transition_audio, content_audio, crossfade_samples)

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def phrase_count(self) -> int:
        return len(self._cached_audio)
