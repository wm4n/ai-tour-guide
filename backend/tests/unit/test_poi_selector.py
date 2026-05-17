"""Unit tests for POISelectorService."""
import pytest
from tour_guide.api.narration import POICandidate, PreviousSelection
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.services.poi_selector import POISelectorService


def make_fake_llm(response: str):
    from unittest.mock import MagicMock

    fake = MagicMock()

    async def _chat_stream(*args, **kwargs):
        yield response

    fake.chat_stream = _chat_stream
    return fake


@pytest.fixture
def fake_persona():
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔"},
        voice={"zh-TW": "zh-TW-YunJheNeural"},
        voice_style=VoiceStyle(speaking_rate=1.0, emotion="neutral"),
        style_profile=StyleProfile(embellishment=0.0, preferred_topics=[]),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔"},
        narration_template={"zh-TW": "narrate {poi_name}"},
        qa_template={"zh-TW": "answer"},
        no_data_context={"zh-TW": "不熟"},
    )


@pytest.mark.asyncio
async def test_selector_returns_valid_poi_id(fake_persona):
    candidates = [
        POICandidate(poi_id="node/1", poi_name="故宮", distance_m=80, wiki_extract="故宮介紹"),
        POICandidate(poi_id="node/2", poi_name="中正紀念堂", distance_m=300, wiki_extract="介紹"),
    ]
    llm = make_fake_llm("node/1")
    service = POISelectorService(llm=llm)
    selected = await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW")
    assert selected == "node/1"


@pytest.mark.asyncio
async def test_selector_falls_back_to_first_candidate_on_invalid_response(fake_persona):
    candidates = [
        POICandidate(poi_id="node/A", poi_name="景點A", distance_m=50, wiki_extract="info"),
        POICandidate(poi_id="node/B", poi_name="景點B", distance_m=200, wiki_extract="info"),
    ]
    llm = make_fake_llm("some_nonexistent_id")
    service = POISelectorService(llm=llm)
    selected = await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW")
    assert selected == "node/A"


@pytest.mark.asyncio
async def test_selector_includes_previous_selection_context(fake_persona):
    candidates = [POICandidate(poi_id="node/1", poi_name="故宮", distance_m=80, wiki_extract="info")]
    previous = PreviousSelection(poi_id="node/old", poi_name="舊景點", script="上次講了很多關於歷史...")
    captured_messages = []

    from unittest.mock import MagicMock

    fake_llm = MagicMock()

    async def _chat_stream(messages, opts):
        captured_messages.extend(messages)
        yield "node/1"

    fake_llm.chat_stream = _chat_stream
    service = POISelectorService(llm=fake_llm)
    await service.select(candidates=candidates, persona=fake_persona, lang="zh-TW", previous=previous)
    user_msg = next(m for m in captured_messages if m.role == "user")
    assert "舊景點" in user_msg.content
    assert "上次講了很多關於歷史" in user_msg.content
