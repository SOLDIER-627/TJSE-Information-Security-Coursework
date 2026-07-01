"""Tests for TTS module (edge-tts fallback only)."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.tts.cosyvoice_tts import CosyVoiceTTS
from src.tts.streaming_tts import normalize_tts_text


def test_tts_init():
    """Test TTS initialization."""
    tts = CosyVoiceTTS(
        model_dir="",
        fallback="edge-tts",
        edge_voice="zh-CN-XiaoxiaoNeural",
    )
    assert tts._fallback == "edge-tts"


def test_normalize_tts():
    """Test pronunciation normalization for shipbuilding terms."""
    assert normalize_tts_text("艏楼结构") == "首楼结构"
    assert normalize_tts_text("艉轴密封") == "尾轴密封"
    assert normalize_tts_text("普通文本") == "普通文本"
    assert normalize_tts_text("艏和艉") == "首和尾"


def test_streaming_normalize():
    """Test streaming TTS normalization (same function)."""
    assert normalize_tts_text("艏柱设计") == "首柱设计"


if __name__ == "__main__":
    test_tts_init()
    test_normalize_tts()
    test_streaming_normalize()
    print("All TTS tests passed!")
