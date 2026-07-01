from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class BaseLLM(ABC):
    """Abstract interface for LLM (Large Language Model) modules."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Generate response text (non-streaming).

        Args:
            prompt: User input prompt.
            system_prompt: System instruction.
            max_tokens: Maximum tokens to generate.
            temperature: Sampling temperature.

        Returns:
            Generated text string.
        """
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Generate response as a stream of text chunks.

        Yields:
            Text chunks as they are generated.
        """
        ...

    @abstractmethod
    def set_api_config(self, api_base: str, api_key: str, model: str) -> None:
        """Configure API endpoint and credentials."""
        ...
