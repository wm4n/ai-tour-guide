"""Smoke tests for real provider implementations.

These tests hit real external services (Gemini, Overpass, Wikipedia)
and are only run with `pytest -m real_provider`.
They require GEMINI_API_KEY to be set in the environment.
"""

import pytest

from tour_guide.providers.llm import LiteLLMAdapter, LlmOpts, Message
from tour_guide.providers.tts import GeminiTtsAdapter, TtsOpts

pytestmark = pytest.mark.real_provider


@pytest.mark.real_provider
async def test_litellm_adapter_streams_text(real_api_key):
    """Test that LiteLLMAdapter streams text chunks from Gemini."""
    adapter = LiteLLMAdapter(api_key=real_api_key)
    messages = [Message(role="user", content="Say 'hello' in exactly one word.")]
    opts = LlmOpts(max_tokens=50)

    chunks = []
    async for chunk in adapter.chat_stream(messages, opts):
        chunks.append(chunk)

    assert len(chunks) > 0
    combined = "".join(chunks)
    assert len(combined) > 0


@pytest.mark.real_provider
async def test_gemini_tts_adapter_yields_audio(real_api_key):
    """Test that GeminiTtsAdapter yields audio bytes."""
    adapter = GeminiTtsAdapter(api_key=real_api_key)
    opts = TtsOpts(speaking_rate=1.0)

    audio_chunks = []
    async for chunk in adapter.synthesize("Hello world.", "Charon", opts):
        audio_chunks.append(chunk)

    assert len(audio_chunks) > 0
    combined = b"".join(audio_chunks)
    assert len(combined) > 0
