from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

import litellm


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LlmOpts:
    model: str = "gemini/gemini-2.0-flash"
    temperature: float = 0.7
    max_tokens: int = 2048


class LlmProvider(Protocol):
    async def chat_stream(
        self,
        messages: list[Message],
        opts: LlmOpts,
    ) -> AsyncIterator[str]: ...


class LiteLLMAdapter:
    """Real LLM provider using LiteLLM with Gemini Flash."""

    def __init__(self, api_key: str, model: str = "gemini/gemini-2.0-flash"):
        self._api_key = api_key
        self._model = model

    async def chat_stream(
        self,
        messages: list[Message],
        opts: LlmOpts,
    ) -> AsyncIterator[str]:
        litellm_messages = [{"role": m.role, "content": m.content} for m in messages]

        response = await litellm.acompletion(
            model=opts.model or self._model,
            messages=litellm_messages,
            stream=True,
            api_key=self._api_key,
            temperature=opts.temperature,
            max_tokens=opts.max_tokens,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content
