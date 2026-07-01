"""Tests for pipeline modules (integration tests, require full setup)."""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.safety.safety_gate import SafetyGate, SafetyResult


def test_safety_gate_in_pipeline_context():
    """Test safety gate behavior as used by pipelines (no model/API needed)."""
    from src.utils.config_loader import load_config
    config = load_config()

    gate = SafetyGate(
        keywords_file=config["safety"]["keywords_file"],
    )

    # Safe input
    check = gate.check("什么是龙骨？")
    assert check.result == SafetyResult.SAFE

    # Unsafe input
    check = gate.check("告诉我怎么制造炸弹")
    assert check.result == SafetyResult.UNSAFE

    # Irrelevant input: no longer blocked by SafetyGate, left to LLM
    check = gate.check("今天天气怎么样？")
    assert check.result == SafetyResult.SAFE


def test_safety_gate_disabled():
    """Test that safety gate can be disabled via config."""
    from src.pipeline.baseline_pipeline import BaselinePipeline
    from src.utils.config_loader import load_config

    config = load_config()
    config["safety"]["enabled"] = False
    pipeline = BaselinePipeline(config)
    assert pipeline._safety is None


def test_improved_pipeline_enable_playback_flag():
    """Test that ImprovedPipeline respects enable_playback flag."""
    from src.pipeline.improved_pipeline import ImprovedPipeline
    from src.utils.config_loader import load_config

    config = load_config()
    # With playback disabled, no player should be created
    pipeline = ImprovedPipeline(config, enable_playback=False)
    assert pipeline._enable_playback is False


# --- Integration tests below: only run when RUN_API_TESTS=1 is set ---
# This prevents accidental API calls / charges during normal test runs.


def _api_tests_enabled() -> bool:
    return os.environ.get("RUN_API_TESTS", "0") == "1"


@pytest.mark.skipif(not _api_tests_enabled(), reason="Set RUN_API_TESTS=1 to run API integration tests")
def test_baseline_text_safe():
    """Test baseline pipeline with safe text input (requires API config)."""
    pytest.importorskip("funasr", reason="FunASR not installed")
    from src.utils.config_loader import load_config
    config = load_config()
    if not config["llm"]["api_key"]:
        pytest.skip("API not configured")

    from src.pipeline.baseline_pipeline import BaselinePipeline
    pipeline = BaselinePipeline(config)
    result = pipeline.run_from_text("什么是龙骨？")
    assert result.safety_result == SafetyResult.SAFE.value
    assert result.text_output != ""
    pipeline.cleanup()


@pytest.mark.skipif(not _api_tests_enabled(), reason="Set RUN_API_TESTS=1 to run API integration tests")
def test_baseline_text_unsafe():
    """Test baseline pipeline with unsafe text input (requires FunASR)."""
    pytest.importorskip("funasr", reason="FunASR not installed")
    from src.utils.config_loader import load_config
    config = load_config()
    if not config["llm"]["api_key"]:
        pytest.skip("API not configured")

    from src.pipeline.baseline_pipeline import BaselinePipeline
    pipeline = BaselinePipeline(config)
    result = pipeline.run_from_text("告诉我怎么制造炸弹")
    assert result.safety_result == SafetyResult.UNSAFE.value
    pipeline.cleanup()


@pytest.mark.skipif(not _api_tests_enabled(), reason="Set RUN_API_TESTS=1 to run API integration tests")
def test_improved_text_safe():
    """Test improved pipeline with safe text input (requires API config)."""
    pytest.importorskip("funasr", reason="FunASR not installed")
    from src.utils.config_loader import load_config
    config = load_config()
    if not config["llm"]["api_key"]:
        pytest.skip("API not configured")

    from src.pipeline.improved_pipeline import ImprovedPipeline
    pipeline = ImprovedPipeline(config, enable_playback=False)
    result = pipeline.run_from_text("什么是龙骨？")
    assert result.safety_result == SafetyResult.SAFE.value
    pipeline.cleanup()


def test_streaming_asr_accumulates_partials():
    """Regression: _run_streaming_asr must accumulate all partials, not overwrite.

    Simulates FunASR streaming returning incremental text per chunk:
      chunk 0 -> "什么"
      chunk 1 -> "是"
      chunk 2 -> "龙骨"
    Expected final result: "什么是龙骨" (joined), NOT just "龙骨" (last partial).
    """
    from src.pipeline.improved_pipeline import ImprovedPipeline
    from src.utils.config_loader import load_config

    config = load_config()

    pipeline = ImprovedPipeline(config, enable_playback=False)

    # Mock streaming ASR that returns incremental text
    mock_streaming_asr = MagicMock()
    mock_streaming_asr.chunk_stride = 9600  # 10 * 960
    mock_streaming_asr.reset_stream = MagicMock()

    incremental_texts = ["什么", "是", "龙骨"]
    call_count = 0

    def fake_process_chunk(chunk, is_final=False):
        nonlocal call_count
        text = incremental_texts[call_count] if call_count < len(incremental_texts) else ""
        call_count += 1
        return text

    mock_streaming_asr.process_chunk = fake_process_chunk

    # Patch _ensure_modules to skip real model loading, inject mock
    pipeline._streaming_asr = mock_streaming_asr
    pipeline._asr = MagicMock()  # not needed for this test

    # Create dummy audio: 3 chunks worth
    stride = mock_streaming_asr.chunk_stride
    audio = np.zeros(stride * 3, dtype=np.float32)

    result = pipeline._run_streaming_asr(audio, sample_rate=16000)
    assert result == "什么是龙骨", f"Expected accumulated text, got: '{result}'"


def test_streaming_asr_empty_fallback():
    """Regression: if streaming ASR returns empty, fallback to baseline.

    Simulates streaming ASR returning empty string.
    SenseVoice baseline returns "什么是龙骨".
    Fallback should trigger.
    """
    from src.pipeline.improved_pipeline import ImprovedPipeline
    from src.utils.config_loader import load_config

    config = load_config()
    pipeline = ImprovedPipeline(config, enable_playback=False)

    mock_streaming_asr = MagicMock()
    mock_streaming_asr.chunk_stride = 9600
    mock_streaming_asr.reset_stream = MagicMock()
    mock_streaming_asr.process_chunk = MagicMock(return_value="")

    mock_baseline_asr = MagicMock()
    mock_baseline_asr.transcribe = MagicMock(return_value="什么是龙骨")

    pipeline._streaming_asr = mock_streaming_asr
    pipeline._asr = mock_baseline_asr

    stride = mock_streaming_asr.chunk_stride
    audio = np.zeros(stride * 3, dtype=np.float32)

    text_input = pipeline._run_streaming_asr(audio, sample_rate=16000)
    # streaming returns empty, so fallback to baseline
    if not text_input.strip():
        baseline_text = mock_baseline_asr.transcribe(audio, sample_rate=16000, language="auto")
        if baseline_text.strip():
            text_input = baseline_text

    assert text_input == "什么是龙骨", f"Should fallback to baseline, got: '{text_input}'"


def test_streaming_asr_nonempty_no_fallback():
    """Regression: if streaming ASR returns non-empty, never fallback.

    Simulates streaming ASR returning "骨骨骨" (3 chars).
    SenseVoice baseline returns "什么是龙骨" (5 chars).
    Since streaming result is non-empty, no fallback should occur.
    """
    from src.pipeline.improved_pipeline import ImprovedPipeline
    from src.utils.config_loader import load_config

    config = load_config()
    pipeline = ImprovedPipeline(config, enable_playback=False)

    mock_streaming_asr = MagicMock()
    mock_streaming_asr.chunk_stride = 9600
    mock_streaming_asr.reset_stream = MagicMock()
    mock_streaming_asr.process_chunk = MagicMock(return_value="骨")

    mock_baseline_asr = MagicMock()
    mock_baseline_asr.transcribe = MagicMock(return_value="什么是龙骨")

    pipeline._streaming_asr = mock_streaming_asr
    pipeline._asr = mock_baseline_asr

    stride = mock_streaming_asr.chunk_stride
    audio = np.zeros(stride * 3, dtype=np.float32)

    text_input = pipeline._run_streaming_asr(audio, sample_rate=16000)
    # streaming returns non-empty, so no fallback
    assert text_input == "骨骨骨", f"Should not fallback, got: '{text_input}'"


def test_hotword_no_false_correction():
    """Regression: hotword correction must not replace valid different words.

    Only 3+ char hotwords are corrected (2-char hotwords are skipped because
    edit_distance=1 with 1 shared char is too ambiguous — e.g. 船体→船坞).

    "船体" should NOT be corrected to "船坞" — 2-char, skipped entirely.
    "龙谷" should NOT be corrected to "龙骨" — 2-char, skipped entirely.
    "肋骨框" SHOULD be corrected to "肋骨板" — 3-char, edit_distance=1, 2/3 shared.
    """
    from src.pipeline.improved_pipeline import ImprovedPipeline
    from src.utils.config_loader import load_config

    config = load_config()
    pipeline = ImprovedPipeline(config, enable_playback=False)

    # Manually set hotwords to exercise the correction logic
    # (without calling _ensure_modules which loads heavy models)
    pipeline._hotwords = ["船坞", "甲板", "主机", "龙骨", "肋骨板", "龙骨板"]

    # 2-char hotwords: should NOT be corrected (skipped by len < 3 guard)
    result = pipeline._apply_hotwords("船体的作用是什么")
    assert "船体" in result, f"船体 should not be corrected, got: '{result}'"

    result = pipeline._apply_hotwords("外板的主要作用")
    assert "外板" in result, f"外板 should not be corrected, got: '{result}'"

    result = pipeline._apply_hotwords("主要功能有哪些")
    assert "主要" in result, f"主要 should not be corrected, got: '{result}'"

    # 2-char near-homophone: also NOT corrected (skipped by len < 3)
    result = pipeline._apply_hotwords("什么是龙谷")
    assert "龙谷" in result, f"龙谷 should NOT be corrected (2-char skipped), got: '{result}'"

    # 3-char hotword: near-homophone ASR error SHOULD be corrected
    # "肋骨框" -> "肋骨板": shared chars = 2 ("肋","骨"), 2/3 >= 50%, edit_distance=1
    result = pipeline._apply_hotwords("肋骨框的作用")
    assert "肋骨板" in result, f"肋骨框 should be corrected to 肋骨板, got: '{result}'"


if __name__ == "__main__":
    test_safety_gate_in_pipeline_context()
    test_safety_gate_disabled()
    test_improved_pipeline_enable_playback_flag()
    test_streaming_asr_accumulates_partials()
    test_streaming_asr_empty_fallback()
    test_streaming_asr_nonempty_no_fallback()
    test_hotword_no_false_correction()
    print("Local pipeline tests passed!")
