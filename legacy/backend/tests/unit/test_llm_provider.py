import pytest

from tour_guide.providers.fakes import FakeLlmProvider
from tour_guide.providers.llm import LlmOpts, Message


@pytest.mark.asyncio
async def test_fake_llm_provider_yields_scripted_chunks():
    """FakeLlmProvider yields scripted chunks in order."""
    provider = FakeLlmProvider(["Hello", " world"])
    messages = [Message(role="user", content="test")]
    opts = LlmOpts()

    chunks = []
    async for chunk in provider.chat_stream(messages, opts):
        chunks.append(chunk)

    assert chunks == ["Hello", " world"]


@pytest.mark.asyncio
async def test_fake_llm_provider_resets_on_multiple_calls():
    """Multiple calls to FakeLlmProvider each reset to the beginning."""
    provider = FakeLlmProvider(["Hello", " world"])
    messages = [Message(role="user", content="test")]
    opts = LlmOpts()

    # First call
    chunks1 = []
    async for chunk in provider.chat_stream(messages, opts):
        chunks1.append(chunk)

    # Second call
    chunks2 = []
    async for chunk in provider.chat_stream(messages, opts):
        chunks2.append(chunk)

    assert chunks1 == ["Hello", " world"]
    assert chunks2 == ["Hello", " world"]
