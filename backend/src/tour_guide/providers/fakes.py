from collections.abc import AsyncIterator

from tour_guide.providers.llm import LlmOpts, Message
from tour_guide.providers.tts import TtsOpts


class FakeLlmProvider:
    """Fake LLM provider that yields scripted chunks."""

    def __init__(self, scripted_chunks: list[str]):
        self._chunks = scripted_chunks

    async def chat_stream(
        self,
        messages: list[Message],
        opts: LlmOpts,
    ) -> AsyncIterator[str]:
        """Yield scripted chunks in order."""
        for chunk in self._chunks:
            yield chunk


_SILENT_AUDIO = b"\x00" * 100  # 100 bytes of silence


class FakeTtsProvider:
    """Fake TTS provider that yields fixed silent audio."""

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        opts: TtsOpts,
    ) -> AsyncIterator[bytes]:
        """Yield fixed silent audio regardless of input."""
        yield _SILENT_AUDIO
