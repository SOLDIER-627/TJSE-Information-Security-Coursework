"""Tests for text splitter module."""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.text_splitter import split_sentences, stream_sentences


def test_split_simple():
    text = "什么是龙骨？龙骨是船舶的基础结构。"
    result = split_sentences(text)
    assert len(result) == 2
    assert "龙骨？" in result[0]
    assert "结构。" in result[1]


def test_split_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_split_english():
    text = "What is a bulkhead? It is a vertical partition."
    result = split_sentences(text)
    assert len(result) == 2


def test_split_long_with_clauses():
    text = "纵骨和肋骨的区别是什么，纵骨沿船长方向布置，肋骨沿船宽方向布置。"
    result = split_sentences(text, split_on_clause=True)
    assert len(result) >= 1


def test_stream_sentences():
    chunks = ["什么是", "龙骨？", "龙骨是", "船舶的基础", "结构。"]
    results = list(stream_sentences(iter(chunks)))
    assert len(results) == 2
    assert "龙骨？" in results[0]
    assert "结构。" in results[1]


def test_stream_incomplete():
    chunks = ["这是一段", "没有句号", "的文本"]
    results = list(stream_sentences(iter(chunks)))
    # Should yield remaining buffer as last sentence
    assert len(results) >= 1


if __name__ == "__main__":
    test_split_simple()
    test_split_english()
    test_split_empty()
    test_split_long_with_clauses()
    test_stream_sentences()
    test_stream_incomplete()
    print("All text_splitter tests passed!")
