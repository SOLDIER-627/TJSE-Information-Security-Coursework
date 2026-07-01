#!/usr/bin/env python3
from __future__ import annotations

"""CLI entry point for cascaded voice Q&A system.

Usage:
    python -m src.main baseline [--text "query" | --audio file.wav]
    python -m src.main improved [--text "query" | --audio file.wav]
    python -m src.main interactive [--pipeline baseline|improved]
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config_loader import load_config
from src.pipeline.baseline_pipeline import BaselinePipeline
from src.pipeline.improved_pipeline import ImprovedPipeline


def load_audio(filepath: str) -> tuple[np.ndarray, int]:
    """Load audio file and return (audio, sample_rate)."""
    audio, sr = sf.read(filepath)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)  # Convert to mono
    return audio.astype(np.float32), sr


def main():
    parser = argparse.ArgumentParser(
        description="级联式语音问答系统 (Cascaded Voice Q&A System)"
    )
    subparsers = parser.add_subparsers(dest="mode", help="运行模式")

    # Baseline mode
    baseline_parser = subparsers.add_parser("baseline", help="基线模式（串行）")
    baseline_parser.add_argument("--text", type=str, help="文本输入（跳过ASR）")
    baseline_parser.add_argument("--audio", type=str, help="音频文件输入")
    baseline_parser.add_argument("--config", type=str, help="配置文件路径")

    # Improved mode
    improved_parser = subparsers.add_parser("improved", help="改进模式（流式并行）")
    improved_parser.add_argument("--text", type=str, help="文本输入（跳过ASR）")
    improved_parser.add_argument("--audio", type=str, help="音频文件输入")
    improved_parser.add_argument("--config", type=str, help="配置文件路径")

    # Interactive mode
    interactive_parser = subparsers.add_parser("interactive", help="交互模式")
    interactive_parser.add_argument(
        "--pipeline", choices=["baseline", "improved"], default="improved",
        help="流水线模式 (default: improved)"
    )
    interactive_parser.add_argument("--config", type=str, help="配置文件路径")

    args = parser.parse_args()

    if args.mode is None:
        parser.print_help()
        return

    # Load config
    config = load_config(args.config) if hasattr(args, "config") and args.config else load_config()

    try:
        if args.mode == "baseline":
            pipeline = BaselinePipeline(config)
            run_pipeline(pipeline, args)

        elif args.mode == "improved":
            pipeline = ImprovedPipeline(config)
            run_pipeline(pipeline, args)

        elif args.mode == "interactive":
            if args.pipeline == "baseline":
                pipeline = BaselinePipeline(config)
            else:
                pipeline = ImprovedPipeline(config)
            pipeline.run_interactive()

    except KeyboardInterrupt:
        print("\n已退出")
    except Exception as e:
        print(f"错误: {e}")
        raise
    finally:
        if "pipeline" in dir():
            pipeline.cleanup()


def run_pipeline(pipeline, args):
    """Run pipeline with text or audio input."""
    if args.text:
        result = pipeline.run_from_text(args.text)
    elif args.audio:
        audio, sr = load_audio(args.audio)
        result = pipeline.run_from_audio(audio, sr)
    else:
        print("请提供 --text 或 --audio 输入")
        return

    # Print results
    print("\n=== 结果 ===")
    print(f"输入: {result.text_input}")
    print(f"安全: {result.safety_result}")
    print(f"输出: {result.text_output}")
    print(f"\n=== 延迟 ===")
    summary = result.timer.summary()
    for key, value in summary.items():
        print(f"  {key}: {value:.2f}ms")


if __name__ == "__main__":
    main()
