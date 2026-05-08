from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


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
