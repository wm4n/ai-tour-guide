from unittest.mock import MagicMock, patch

import pytest

from tour_guide.providers.tts import EdgeTtsAdapter, TtsOpts


@pytest.mark.asyncio
async def test_edge_tts_adapter_yields_audio_chunks():
    raw = [
        {"type": "audio", "data": b"chunk1"},
        {"type": "WordBoundary"},
        {"type": "audio", "data": b"chunk2"},
    ]

    async def mock_stream():
        for chunk in raw:
            yield chunk

    mock_communicate = MagicMock()
    mock_communicate.stream = mock_stream
    with patch("tour_guide.providers.tts.edge_tts.Communicate", return_value=mock_communicate):
        adapter = EdgeTtsAdapter()
        chunks = []
        async for chunk in adapter.synthesize("hello", "zh-TW-YunJheNeural", TtsOpts()):
            chunks.append(chunk)
    assert chunks == [b"chunk1", b"chunk2"]


@pytest.mark.asyncio
async def test_edge_tts_adapter_skips_non_audio_chunks():
    raw = [{"type": "WordBoundary"}, {"type": "SessionEnd"}]

    async def mock_stream():
        for chunk in raw:
            yield chunk

    mock_communicate = MagicMock()
    mock_communicate.stream = mock_stream
    with patch("tour_guide.providers.tts.edge_tts.Communicate", return_value=mock_communicate):
        adapter = EdgeTtsAdapter()
        chunks = []
        async for chunk in adapter.synthesize("hello", "en-US-GuyNeural", TtsOpts()):
            chunks.append(chunk)
    assert chunks == []
