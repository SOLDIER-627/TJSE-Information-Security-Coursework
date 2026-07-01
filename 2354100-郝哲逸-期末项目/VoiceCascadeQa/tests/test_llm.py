"""Tests for LLM module (requires API configuration)."""

import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

pytest.importorskip("openai", reason="openai package not installed")

from src.llm.openai_llm import OpenAILLM


def test_llm_init():
    """Test LLM initialization without API call."""
    llm = OpenAILLM(
        api_base="https://api.placeholder.com/v1",
        api_key="sk-placeholder",
        model="deepseek-chat",
    )
    assert llm._api_base == "https://api.placeholder.com/v1"
    assert llm._api_key == "sk-placeholder"
    assert llm._model == "deepseek-chat"


def test_llm_set_config():
    """Test updating API configuration."""
    llm = OpenAILLM()
    llm.set_api_config("https://new-api.com/v1", "sk-new", "qwen-chat")
    assert llm._api_base == "https://new-api.com/v1"
    assert llm._api_key == "sk-new"
    assert llm._model == "qwen-chat"
    assert llm._client is None


if __name__ == "__main__":
    test_llm_init()
    test_llm_set_config()
    print("All LLM tests passed!")
