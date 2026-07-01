"""Tests for config loader module."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.config_loader import load_config


def test_load_default_config():
    config = load_config()
    assert "asr" in config
    assert "llm" in config
    assert "tts" in config
    assert "safety" in config
    assert "device" in config


def test_config_paths_resolved():
    config = load_config()
    # Hotword file should be absolute path
    hotword_file = Path(config["asr"]["hotword_file"])
    assert hotword_file.is_absolute()
    # Safety keywords file should be absolute path
    keywords_file = Path(config["safety"]["keywords_file"])
    assert keywords_file.is_absolute()


def test_config_has_project_root():
    config = load_config()
    assert "_project_root" in config
    assert Path(config["_project_root"]).exists()


if __name__ == "__main__":
    test_load_default_config()
    test_config_paths_resolved()
    test_config_has_project_root()
    print("All config loader tests passed!")
