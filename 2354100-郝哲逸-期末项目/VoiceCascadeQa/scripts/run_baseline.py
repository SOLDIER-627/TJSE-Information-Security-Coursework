#!/usr/bin/env python3
"""Run baseline evaluation on test audio set.

Features:
- Incremental save: each run result is appended to CSV immediately
- Resume support: tracks (test_id, run) pairs to fill missing runs
- Schema validation: backs up old CSV if header mismatch
- Detailed logging: prints latency breakdown for each run
"""

import csv
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(scripts_dir))

import numpy as np
import soundfile as sf

from src.utils.config_loader import load_config
from src.pipeline.baseline_pipeline import BaselinePipeline
from eval_utils import validate_csv_header, backup_and_remove, load_completed_runs, get_missing_runs, append_result


def load_audio(filepath: Path) -> tuple[np.ndarray, int]:
    """Load audio file (WAV format expected)."""
    audio, sr = sf.read(str(filepath))
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio.astype(np.float32), sr


def print_detailed_log(test_id: str, run: int, total_runs: int, result: dict) -> None:
    """Print detailed latency breakdown for a single run."""
    print(f"\n  Run {run}/{total_runs}:")
    print(f"    text_input: {result['text_input']}")
    print(f"    safety: {result['safety_result']}")
    print(f"    asr_latency: {result['latency_asr_latency']:.1f}ms")
    print(f"    safety_latency: {result['latency_safety_latency']:.1f}ms")
    print(f"    llm_first_sentence: {result['latency_llm_first_sentence']:.1f}ms")
    print(f"    tts_first_chunk: {result['latency_tts_first_chunk']:.1f}ms")
    print(f"    first_playable: {result['latency_first_playable']:.1f}ms")
    print(f"    wall_total: {result['latency_wall_total']:.1f}ms")


def main():
    config = load_config()
    runs_per_audio = config["evaluation"]["runs_per_audio"]
    output_dir = Path(config["evaluation"]["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_dir = project_root / "data" / "audio_test_set"
    metadata_path = audio_dir / "metadata.csv"
    output_path = output_dir / "baseline_results.csv"

    if not metadata_path.exists():
        print("Error: Test audio set not found. Run scripts/prepare_test_audio.py first.")
        return

    # Fieldnames for CSV
    fieldnames = [
        "test_id", "category", "run", "text_input", "text_output",
        "safety_result", "latency_asr_latency", "latency_safety_latency",
        "latency_llm_first_sentence", "latency_tts_first_chunk",
        "latency_first_playable", "latency_total_response", "latency_wall_total",
    ]

    # Schema validation: check if existing CSV header matches
    if not validate_csv_header(output_path, fieldnames):
        bak_path = backup_and_remove(output_path)
        print(f"[WARN] CSV schema mismatch, old file backed up to {bak_path}")
        print(f"       Starting fresh evaluation.\n")

    # Load existing results for resume (tracks exact run numbers)
    completed = load_completed_runs(output_path)

    # Load metadata
    test_cases = []
    with open(metadata_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_cases.append(row)

    total_records = sum(len(runs) for runs in completed.values())
    print(f"=== 基线评测 ===")
    print(f"测试用例: {len(test_cases)}")
    print(f"每条运行次数: {runs_per_audio}")
    print(f"已有结果: {total_records} 条记录")
    print(f"输出文件: {output_path}\n")

    pipeline = BaselinePipeline(config)

    total_completed = 0
    total_skipped = 0

    for i, case in enumerate(test_cases):
        test_id = case["id"]
        category = case["category"]

        missing = get_missing_runs(test_id, completed, runs_per_audio)

        if not missing:
            done_count = len(completed.get(test_id, set()))
            print(f"[SKIP] {test_id} already completed {done_count}/{runs_per_audio} runs")
            total_skipped += 1
            continue

        done_count = len(completed.get(test_id, set()))
        if done_count > 0:
            print(f"[RESUME] {test_id} completed {done_count}/{runs_per_audio}, missing runs: {missing}")
        else:
            print(f"[{i+1}/{len(test_cases)}] {test_id} ({category})")

        # Try to load audio file
        audio_path = audio_dir / f"{test_id}.wav"
        if not audio_path.exists():
            audio_path = audio_dir / f"{test_id}.mp3"

        if not audio_path.exists():
            print(f"  WARNING: Audio file not found for {test_id}, skipping")
            continue

        audio, sr = load_audio(audio_path)

        for run in missing:
            try:
                wall_start = time.perf_counter()
                result = pipeline.run_from_audio(audio, sr)
                wall_total_ms = (time.perf_counter() - wall_start) * 1000

                summary = result.timer.summary()
                row = {
                    "test_id": test_id,
                    "category": category,
                    "run": run,
                    "text_input": result.text_input,
                    "text_output": result.text_output[:100] if result.text_output else "",
                    "safety_result": result.safety_result,
                    "latency_asr_latency": round(summary.get("asr_latency", 0), 2),
                    "latency_safety_latency": round(summary.get("safety_latency", 0), 2),
                    "latency_llm_first_sentence": round(summary.get("llm_first_sentence", 0), 2),
                    "latency_tts_first_chunk": round(summary.get("tts_first_chunk", 0), 2),
                    "latency_first_playable": round(summary.get("first_playable", 0), 2),
                    "latency_total_response": round(summary.get("total_response", 0), 2),
                    "latency_wall_total": round(wall_total_ms, 2),
                }

                # Append immediately
                append_result(output_path, row, fieldnames)
                total_completed += 1

                # Track in completed dict for consistency
                completed.setdefault(test_id, set()).add(run)

                # Print detailed log
                print_detailed_log(test_id, run, runs_per_audio, row)

            except Exception as e:
                print(f"  ERROR on run {run}: {e}")
                continue

    print(f"\n=== 评测完成 ===")
    print(f"完成: {total_completed} 条记录")
    print(f"跳过: {total_skipped} 条（已存在）")
    print(f"结果保存: {output_path}")
    pipeline.cleanup()


if __name__ == "__main__":
    main()