#!/usr/bin/env python3
"""Compare baseline vs improved pipeline results.

Reads baseline_results.csv and improved_results.csv from data/results/,
computes mean±std for each metric, and prints a comparison table.
Also saves comparison.csv and per-category breakdown.

Handles incremental/resumed CSV files where metric columns may differ
between baseline and improved (e.g., first_content only in improved).
"""

import sys
from pathlib import Path

import pandas as pd

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))


# Metrics to compare (union of baseline and improved metrics)
METRICS = [
    ("latency_asr_latency", "ASR 延迟"),
    ("latency_safety_latency", "安全检查延迟"),
    ("latency_llm_first_sentence", "LLM 首句延迟"),
    ("latency_tts_first_chunk", "TTS 首块延迟"),
    ("latency_first_playable", "首段可播放延迟"),
    ("latency_first_content", "正文首段延迟"),
    ("latency_total_response", "总响应时间"),
    ("latency_wall_total", "完整运行耗时"),
]


def load_results(filepath: Path) -> pd.DataFrame:
    """Load results CSV, returning empty DataFrame if file missing."""
    if not filepath.exists():
        return pd.DataFrame()
    return pd.read_csv(filepath)


def compute_stats(df: pd.DataFrame, metric: str) -> str:
    """Compute mean±std for a metric, return formatted string or N/A."""
    if metric not in df.columns or df.empty:
        return "N/A"
    vals = df[metric].dropna()
    if vals.empty:
        return "N/A"
    return f"{vals.mean():.1f}±{vals.std():.1f}"


def main():
    results_dir = project_root / "data" / "results"

    baseline_df = load_results(results_dir / "baseline_results.csv")
    improved_df = load_results(results_dir / "improved_results.csv")

    if baseline_df.empty and improved_df.empty:
        print("No result files found. Run run_baseline.py and run_improved.py first.")
        return

    # Overall comparison table
    rows = []
    for metric_key, metric_name in METRICS:
        b_stat = compute_stats(baseline_df, metric_key)
        i_stat = compute_stats(improved_df, metric_key)

        ratio = "—"
        if b_stat != "N/A" and i_stat != "N/A":
            try:
                b_mean = float(b_stat.split("±")[0])
                i_mean = float(i_stat.split("±")[0])
                if b_mean > 0:
                    pct = (b_mean - i_mean) / b_mean * 100
                    ratio = f"{pct:+.1f}%"
            except (ValueError, ZeroDivisionError):
                pass

        rows.append({
            "指标 (ms)": metric_name,
            "基线 (mean±std)": b_stat,
            "改进 (mean±std)": i_stat,
            "提升比例": ratio,
        })

    comparison_df = pd.DataFrame(rows)

    print("\n" + "=" * 70)
    print("基线 vs 改进 延迟对比表")
    print("=" * 70)
    print(comparison_df.to_string(index=False))
    print("=" * 70)
    print("\n注：first_content 仅为改进版指标，基线值记为 N/A")

    comparison_df.to_csv(results_dir / "comparison.csv", index=False, encoding="utf-8-sig")
    print(f"\n对比表已保存: {results_dir / 'comparison.csv'}")

    # Per-category breakdown
    if "category" in improved_df.columns and not improved_df.empty:
        print("\n" + "=" * 70)
        print("分类延迟对比（首段可播放延迟 first_playable）")
        print("=" * 70)

        categories = set()
        if not baseline_df.empty:
            categories.update(baseline_df["category"].unique())
        if not improved_df.empty:
            categories.update(improved_df["category"].unique())
        categories = sorted(categories)

        cat_rows = []
        for cat in categories:
            b_sub = baseline_df[baseline_df["category"] == cat] if not baseline_df.empty else pd.DataFrame()
            i_sub = improved_df[improved_df["category"] == cat] if not improved_df.empty else pd.DataFrame()

            b_fp = compute_stats(b_sub, "latency_first_playable")
            i_fp = compute_stats(i_sub, "latency_first_playable")
            i_fc = compute_stats(i_sub, "latency_first_content")

            cat_rows.append({
                "类别": cat,
                "基线 first_playable": b_fp,
                "改进 first_playable": i_fp,
                "改进 first_content": i_fc,
            })

        cat_df = pd.DataFrame(cat_rows)
        print(cat_df.to_string(index=False))
        print("=" * 70)

        cat_df.to_csv(results_dir / "comparison_by_category.csv", index=False, encoding="utf-8-sig")
        print(f"分类对比已保存: {results_dir / 'comparison_by_category.csv'}")


if __name__ == "__main__":
    main()
