from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class SafetyResult(Enum):
    SAFE = "safe"
    UNSAFE = "unsafe"


@dataclass
class SafetyCheck:
    result: SafetyResult
    category: Optional[str] = None
    matched_keyword: Optional[str] = None
    reason: str = ""


class SafetyGate:
    """Safety gate for filtering harmful/malicious input.

    Only checks for UNSAFE content (violence, injection, etc.).
    Domain relevance is left to the LLM's system prompt — ASR misrecognition
    makes keyword-based relevance checking unreliable (e.g. "艏楼"→"手楼").
    """

    def __init__(
        self,
        keywords_file: Optional[str] = None,
    ):
        self._keywords: dict[str, list[str]] = {}

        if keywords_file:
            self.load_keywords(keywords_file)

    def load_keywords(self, filepath: str) -> None:
        """Load safety keywords from file.

        File format: category|keyword1,keyword2,...
        """
        path = Path(filepath)
        if not path.exists():
            print(f"[Safety] Keywords file not found: {filepath}")
            return

        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "|" in line:
                    category, keywords = line.split("|", 1)
                    self._keywords[category.strip()] = [
                        kw.strip().lower() for kw in keywords.split(",") if kw.strip()
                    ]

    def check(self, text: str) -> SafetyCheck:
        """Check text for safety violations (UNSAFE only).

        Domain relevance is no longer checked here — ASR misrecognition
        causes too many false IRRELEVANT results. The LLM's system prompt
        handles off-domain queries gracefully.

        Returns:
            SafetyCheck with result, category, matched keyword, and reason.
        """
        text_lower = text.lower()

        # Check against keyword categories (skip "irrelevant" category)
        for category, keywords in self._keywords.items():
            if category == "irrelevant":
                continue
            for kw in keywords:
                if kw in text_lower:
                    return SafetyCheck(
                        result=SafetyResult.UNSAFE,
                        category=category,
                        matched_keyword=kw,
                        reason=f"检测到不安全内容 ({category}): {kw}",
                    )

        return SafetyCheck(result=SafetyResult.SAFE, reason="内容安全")

    def is_safe(self, text: str) -> bool:
        """Quick check if text is safe (no blocking needed)."""
        result = self.check(text)
        return result.result == SafetyResult.SAFE
