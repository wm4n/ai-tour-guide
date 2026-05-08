from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol


@dataclass
class TtsOpts:
    speaking_rate: float = 1.0
    emotion: str = "neutral"


class TtsProvider(Protocol):
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        opts: TtsOpts,
    ) -> AsyncIterator[bytes]: ...
