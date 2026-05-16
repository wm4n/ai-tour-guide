"""Tests for NarrationService no-data short-circuit."""

import pytest
from dataclasses import field
from unittest.mock import AsyncMock, MagicMock, patch

from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.models.poi import OsmNode, POIContext
from tour_guide.services.narration_service import (
    AudioEvent,
    EndEvent,
    MetaEvent,
    NarrationService,
    TextEvent,
)


@pytest.fixture
def fake_persona():
    return PersonaConfig(
        id="test_persona",
        display_name={"zh-TW": "測試"},
        voice={"zh-TW": "zh-TW-YunJheNeural"},
        voice_style=VoiceStyle(speaking_rate=1.0, emotion="neutral"),
        style_profile=StyleProfile(embellishment=0.0, preferred_topics=[]),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是測試"},
        narration_template={"zh-TW": "narrate {poi_name} {poi_context} {target_length}"},
        qa_template={"zh-TW": "answer"},
        no_data_context={"zh-TW": "這附近大哥哥也不太熟！"},
    )


@pytest.fixture
def poi_no_wiki():
    osm = OsmNode(
        id="osm:node:1",
        lat=25.04,
        lon=121.53,
        tags={"name": "Unknown Place", "tourism": "attraction"},
    )
    return POIContext(osm=osm, wiki=None)


def make_fake_tts(audio_data: bytes = b"audio_data"):
    """Create a fake TTS provider whose synthesize() is an async generator."""
    fake_tts = MagicMock()
    async def _synthesize(*args, **kwargs):
        yield audio_data
    fake_tts.synthesize = _synthesize
    return fake_tts


def make_fake_llm(chunks: list[str]):
    """Create a fake LLM provider whose chat_stream() is an async generator."""
    fake_llm = MagicMock()
    call_count = 0

    async def _chat_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        for chunk in chunks:
            yield chunk

    fake_llm.chat_stream = _chat_stream
    fake_llm.chat_stream_call_count = lambda: call_count
    return fake_llm


@pytest.mark.asyncio
async def test_no_data_short_circuit_skips_llm(fake_persona, poi_no_wiki):
    """When wiki is None and no_data_context exists, LLM is not called."""
    fake_llm = make_fake_llm([])
    fake_tts = make_fake_tts()

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi_no_wiki, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    assert fake_llm.chat_stream_call_count() == 0
    assert any(isinstance(e, TextEvent) for e in events)
    assert any(isinstance(e, AudioEvent) for e in events)
    assert any(isinstance(e, EndEvent) for e in events)


@pytest.mark.asyncio
async def test_no_data_short_circuit_uses_no_data_text(fake_persona, poi_no_wiki):
    """The TextEvent chunk should be the no_data_context text."""
    fake_llm = make_fake_llm([])
    fake_tts = make_fake_tts()

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi_no_wiki, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, TextEvent)]
    assert len(text_events) == 1
    assert text_events[0].chunk == "這附近大哥哥也不太熟！"


@pytest.mark.asyncio
async def test_no_data_fallback_not_triggered_when_wiki_exists(fake_persona):
    """When wiki is present, normal LLM path is used (LLM is called)."""
    from tour_guide.models.poi import WikiArticle
    osm = OsmNode(id="osm:node:2", lat=25.0, lon=121.5, tags={"name": "故宮", "tourism": "museum"})
    wiki = WikiArticle(title="故宮", extract="故宮是...", url="", lang="zh-TW")
    poi = POIContext(osm=osm, wiki=wiki)

    fake_llm = make_fake_llm(["故宮是一個博物館。"])
    fake_tts = make_fake_tts()

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    assert fake_llm.chat_stream_call_count() == 1
