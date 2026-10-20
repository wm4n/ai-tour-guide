"""Unit tests for FakeSttProvider."""

import pytest

from tour_guide.providers.stt import FakeSttProvider


class TestFakeSttProvider:
    @pytest.mark.asyncio
    async def test_returns_scripted_text(self):
        stt = FakeSttProvider("這是故宮博物院嗎？")
        result = await stt.transcribe(b"\x00" * 100, "zh-TW")
        assert result == "這是故宮博物院嗎？"

    @pytest.mark.asyncio
    async def test_default_text(self):
        stt = FakeSttProvider()
        result = await stt.transcribe(b"\x00" * 100, "en")
        assert isinstance(result, str)
        assert len(result) > 0
