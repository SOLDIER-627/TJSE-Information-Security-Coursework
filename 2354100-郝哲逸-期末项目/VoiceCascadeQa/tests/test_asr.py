"""Tests for ASR module (requires FunASR installed)."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.asr.sensevoice_asr import SenseVoiceASR, FUNASR_AVAILABLE
from src.asr.streaming_asr import StreamingASR


def test_asr_init():
    """Test ASR initialization (without loading model)."""
    if not FUNASR_AVAILABLE:
        print("FunASR not available, skipping ASR init test")
        return
    asr = SenseVoiceASR(device="cpu")
    assert not asr.is_loaded


def test_streaming_asr_init():
    """Test streaming ASR initialization."""
    if not FUNASR_AVAILABLE:
        print("FunASR not available, skipping streaming ASR init test")
        return
    asr = StreamingASR(device="cpu")
    assert not asr.is_loaded
    assert asr.chunk_stride == 10 * 960  # 9600 samples


if __name__ == "__main__":
    test_asr_init()
    test_streaming_asr_init()
    print("All ASR tests passed!")
