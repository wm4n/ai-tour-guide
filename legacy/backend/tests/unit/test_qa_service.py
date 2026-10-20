"""Unit tests for QAService."""

import pytest

from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.providers.stt import FakeSttProvider
from tour_guide.services.qa_service import QAService, TranscriptEvent


def _make_persona() -> PersonaConfig:
    return PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔"},
        voice={"zh-TW": "Charon"},
        voice_style=VoiceStyle(),
        style_profile=StyleProfile(),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔。"},
        narration_template={"zh-TW": "narrate {poi_name}"},
        qa_template={
            "zh-TW": "{system_prompt}\n{poi_name}\n{narration_summary}\n{user_question}",
        },
    )


class TestQAServiceEventOrder:
    @pytest.mark.asyncio
    async def test_first_event_is_transcript(self):
        stt = FakeSttProvider("這裡有多少文物？")
        llm = FakeLlmProvider(["故宮有約七十萬件文物。"])
        tts = FakeTtsProvider()
        service = QAService(stt=stt, llm=llm, tts=tts)

        events = []
        async for event in service.answer(
            audio_bytes=b"\x00" * 100,
            persona=_make_persona(),
            lang="zh-TW",
            current_poi_name="故宮博物院",
            narration_so_far="故宮是台灣最重要的博物館。",
        ):
            events.append(event)

        assert len(events) > 0
        assert isinstance(events[0], TranscriptEvent)
        assert events[0].text == "這裡有多少文物？"

    @pytest.mark.asyncio
    async def test_last_event_is_end(self):
        from tour_guide.services.qa_service import EndEvent
        stt = FakeSttProvider("問題")
        llm = FakeLlmProvider(["回答。"])
        tts = FakeTtsProvider()
        service = QAService(stt=stt, llm=llm, tts=tts)

        events = []
        async for event in service.answer(
            audio_bytes=b"\x00" * 100,
            persona=_make_persona(),
            lang="zh-TW",
            current_poi_name=None,
            narration_so_far="",
        ):
            events.append(event)

        assert isinstance(events[-1], EndEvent)

    @pytest.mark.asyncio
    async def test_audio_events_are_present(self):
        from tour_guide.services.qa_service import AudioEvent
        stt = FakeSttProvider("問題")
        llm = FakeLlmProvider(["回答一。回答二。"])
        tts = FakeTtsProvider()
        service = QAService(stt=stt, llm=llm, tts=tts)

        events = []
        async for event in service.answer(
            audio_bytes=b"\x00" * 100,
            persona=_make_persona(),
            lang="zh-TW",
            current_poi_name="故宮",
            narration_so_far="",
        ):
            events.append(event)

        audio_events = [e for e in events if isinstance(e, AudioEvent)]
        assert len(audio_events) > 0
