"""Tests for timer module."""

import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.timer import Timer


def test_timer_basic():
    timer = Timer()
    timer.start()
    timer.mark("step1")
    timer.mark("step2")
    timer.mark("step3")

    checkpoints = timer.all_checkpoints()
    assert len(checkpoints) == 4  # t_start + 3 marks
    assert checkpoints[0].name == "t_start"


def test_timer_elapsed():
    timer = Timer()
    timer.start()
    timer.mark("a")
    time.sleep(0.01)
    timer.mark("b")

    elapsed = timer.elapsed("a", "b")
    assert elapsed is not None
    assert elapsed >= 10  # At least 10ms


def test_timer_summary():
    timer = Timer()
    timer.start()
    timer.mark("t_user_silent")
    timer.mark("t_asr_complete")
    timer.mark("t_safety_check")
    timer.mark("t_llm_first_sentence")
    timer.mark("t_tts_first_chunk")
    timer.mark("t_first_playable")
    timer.finish()

    summary = timer.summary()
    assert "asr_latency" in summary
    assert "safety_latency" in summary
    assert "first_playable" in summary
    assert "wall_total" in summary
    assert summary["asr_latency"] >= 0
    assert summary["safety_latency"] >= 0
    assert summary["first_playable"] >= 0
    assert summary["wall_total"] >= 0


def test_timer_not_started():
    timer = Timer()
    try:
        timer.mark("fail")
        assert False, "Should have raised RuntimeError"
    except RuntimeError:
        pass


def test_timer_nonexistent_checkpoint():
    timer = Timer()
    timer.start()
    timer.mark("a")
    assert timer.elapsed("a", "nonexistent") is None


if __name__ == "__main__":
    test_timer_basic()
    test_timer_elapsed()
    test_timer_summary()
    test_timer_not_started()
    test_timer_nonexistent_checkpoint()
    print("All timer tests passed!")
