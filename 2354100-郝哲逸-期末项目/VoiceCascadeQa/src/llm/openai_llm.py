from __future__ import annotations

from typing import AsyncGenerator, Optional

from .base_llm import BaseLLM

try:
    from openai import AsyncOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class OpenAILLM(BaseLLM):
    """OpenAI-compatible LLM client with streaming support.

    Works with DeepSeek, Qwen, and other OpenAI-compatible APIs.
    """

    def __init__(
        self,
        api_base: str = "https://api.openai.com/v1",
        api_key: str = "",
        model: str = "gpt-3.5-turbo",
        default_system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package not installed. Run: pip install openai")
        self._api_base = api_base
        self._api_key = api_key
        self._model = model
        self._default_system_prompt = default_system_prompt
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._client: Optional[OpenAI] = None
        self._async_client: Optional[AsyncOpenAI] = None

    def _ensure_client(self) -> None:
        if self._client is None:
            self._client = OpenAI(
                base_url=self._api_base,
                api_key=self._api_key,
            )
            self._async_client = AsyncOpenAI(
                base_url=self._api_base,
                api_key=self._api_key,
            )

    def set_api_config(self, api_base: str, api_key: str, model: str) -> None:
        self._api_base = api_base
        self._api_key = api_key
        self._model = model
        self._client = None
        self._async_client = None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate response (non-streaming)."""
        self._ensure_client()
        system = system_prompt or self._default_system_prompt
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": self._model, "messages": messages}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        elif self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self._temperature is not None:
            kwargs["temperature"] = self._temperature

        response = self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> AsyncGenerator[str, None]:
        """Generate response as a stream of text chunks."""
        self._ensure_client()
        system = system_prompt or self._default_system_prompt
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": self._model, "messages": messages, "stream": True}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        elif self._max_tokens is not None:
            kwargs["max_tokens"] = self._max_tokens
        if temperature is not None:
            kwargs["temperature"] = temperature
        elif self._temperature is not None:
            kwargs["temperature"] = self._temperature

        stream = await self._async_client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
