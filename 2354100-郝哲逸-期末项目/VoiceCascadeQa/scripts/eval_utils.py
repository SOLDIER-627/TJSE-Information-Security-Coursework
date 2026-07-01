"""Common utilities for evaluation scripts (run_baseline.py, run_improved.py)."""

import csv
import shutil
from pathlib import Path


def validate_csv_header(filepath: Path, fieldnames: list[str]) -> bool:
    """Check if existing CSV header matches expected fieldnames.

    Returns True if header matches. Returns False if file doesn't exist
    (which is fine — we'll create it) or if header mismatches.
    """
    if not filepath.exists():
        return True
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        existing = list(reader.fieldnames or [])
    return existing == fieldnames


def backup_and_remove(filepath: Path) -> Path:
    """Backup existing CSV to .bak and remove the original.

    Returns the backup path.
    """
    backup_path = filepath.with_suffix(filepath.suffix + ".bak")
    shutil.copy2(filepath, backup_path)
    filepath.unlink()
    return backup_path


def load_completed_runs(filepath: Path) -> dict[str, set[int]]:
    """Load existing results and return (test_id, run) pairs.

    Returns:
        Dict mapping test_id -> set of completed run numbers
    """
    if not filepath.exists():
        return {}
    completed = {}
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            test_id = row["test_id"]
            run_num = int(row["run"])
            if test_id not in completed:
                completed[test_id] = set()
            completed[test_id].add(run_num)
    return completed


def get_missing_runs(test_id: str, completed: dict[str, set[int]], runs_per_audio: int) -> list[int]:
    """Get list of run numbers that still need to be executed.

    Returns sorted list of missing run numbers (1-indexed).
    """
    done = completed.get(test_id, set())
    return sorted(r for r in range(1, runs_per_audio + 1) if r not in done)


def append_result(filepath: Path, result: dict, fieldnames: list[str]) -> None:
    """Append a single result row to CSV file."""
    file_exists = filepath.exists() and filepath.stat().st_size > 0
    with open(filepath, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(result)