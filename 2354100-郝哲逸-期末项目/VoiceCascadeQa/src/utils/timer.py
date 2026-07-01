from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Checkpoint:
    name: str
    timestamp: float
    description: str = ""


class Timer:
    """Named checkpoint latency measurement for pipeline profiling."""

    def __init__(self):
        self._checkpoints: list[Checkpoint] = []
        self._start_time: Optional[float] = None

    def start(self) -> "Timer":
        """Start the timer, record initial checkpoint."""
        self._checkpoints.clear()
        self._start_time = time.perf_counter()
        self.mark("t_start", "Timer started")
        return self

    def mark(self, name: str, description: str = "") -> float:
        """Record a named checkpoint, return elapsed ms from start."""
        if self._start_time is None:
            raise RuntimeError("Timer not started. Call start() first.")
        ts = time.perf_counter()
        elapsed_ms = (ts - self._start_time) * 1000
        self._checkpoints.append(Checkpoint(name, elapsed_ms, description))
        return elapsed_ms

    def elapsed(self, from_checkpoint: str, to_checkpoint: str) -> Optional[float]:
        """Get elapsed ms between two named checkpoints."""
        cp_map = {cp.name: cp.timestamp for cp in self._checkpoints}
        if from_checkpoint not in cp_map or to_checkpoint not in cp_map:
            return None
        return cp_map[to_checkpoint] - cp_map[from_checkpoint]

    def get_checkpoint(self, name: str) -> Optional[Checkpoint]:
        """Get checkpoint by name."""
        for cp in self._checkpoints:
            if cp.name == name:
                return cp
        return None

    def all_checkpoints(self) -> list[Checkpoint]:
        """Return all recorded checkpoints."""
        return self._checkpoints.copy()

    def summary(self) -> dict[str, float]:
        """Return summary of key latencies in ms."""
        result = {
            "asr_latency": self.elapsed("t_user_silent", "t_asr_complete") or 0.0,
            "safety_latency": self.elapsed("t_asr_complete", "t_safety_check") or 0.0,
            "llm_first_sentence": self.elapsed("t_asr_complete", "t_llm_first_sentence") or 0.0,
            "tts_first_chunk": self.elapsed("t_llm_first_sentence", "t_tts_first_chunk") or 0.0,
            "first_playable": self.elapsed("t_user_silent", "t_first_playable") or 0.0,
            "total_response": self.elapsed("t_start", "t_first_playable") or 0.0,
            "wall_total": self.elapsed("t_start", "t_end") if self.get_checkpoint("t_end") else 0.0,
        }
        # Add first_content if available (improved pipeline only)
        fc = self.elapsed("t_user_silent", "t_first_content")
        if fc is not None:
            result["first_content"] = fc
        return result

    def finish(self) -> float:
        """Mark the end of the pipeline run, return total wall time in ms."""
        return self.mark("t_end", "Pipeline run complete")

    def __str__(self) -> str:
        lines = ["Timer checkpoints:"]
        for cp in self._checkpoints:
            lines.append(f"  {cp.name}: {cp.timestamp:.2f}ms - {cp.description}")
        return "\n".join(lines)
