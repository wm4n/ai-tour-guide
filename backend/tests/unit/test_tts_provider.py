import pytest

from tour_guide.providers.fakes import FakeTtsProvider
from tour_guide.providers.tts import TtsOpts


@pytest.mark.asyncio
async def test_fake_tts_provider_yields_bytes_chunk():
    """FakeTtsProvider yields at least one non-empty bytes chunk."""
    provider = FakeTtsProvider()
    opts = TtsOpts()

    chunks = []
    async for chunk in provider.synthesize("Hello world", "voice1", opts):
        chunks.append(chunk)

    assert len(chunks) >= 1
    assert all(isinstance(chunk, bytes) for chunk in chunks)
    assert all(len(chunk) > 0 for chunk in chunks)


@pytest.mark.asyncio
async def test_fake_tts_provider_yields_fixed_audio():
    """FakeTtsProvider yields fixed silent audio regardless of input."""
    provider = FakeTtsProvider()
    opts = TtsOpts()

    chunks1 = []
    async for chunk in provider.synthesize("Hello", "voice1", opts):
        chunks1.append(chunk)

    chunks2 = []
    async for chunk in provider.synthesize("Different text", "voice2", opts):
        chunks2.append(chunk)

    # Both calls should yield the same audio
    assert chunks1 == chunks2
