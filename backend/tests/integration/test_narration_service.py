"""Integration tests for NarrationService using fake providers."""

import base64

import pytest

from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.models.poi import OsmNode, POIContext, WikiArticle
from tour_guide.prompts.loader import PersonaLoader
from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.services.narration_service import (
    AudioEvent,
    EndEvent,
    MetaEvent,
    NarrationService,
    TextEvent,
)


@pytest.fixture()
def persona():
    return PersonaLoader.load("history_uncle")


@pytest.fixture()
def poi_with_wiki():
    """POIContext with Wikipedia article for high confidence."""
    osm = OsmNode(
        id="osm:node:123",
        lat=25.0952,
        lon=121.5442,
        tags={"name": "國立故宮博物院", "tourism": "museum"},
    )
    wiki = WikiArticle(
        title="國立故宮博物院",
        extract="國立故宮博物院，位於臺灣臺北市士林區，是中華民國最重要的國家級博物館之一。" * 6,  # noqa: RUF001
        url="https://zh.wikipedia.org/wiki/國立故宮博物院",
        lang="zh-TW",
    )
    return POIContext(osm=osm, wiki=wiki)


@pytest.fixture()
def poi_no_wiki():
    """POIContext without Wikipedia article for low confidence."""
    osm = OsmNode(
        id="osm:node:456",
        lat=25.0952,
        lon=121.5442,
        tags={"name": "某景點"},
    )
    return POIContext(osm=osm, wiki=None)


class TestNarrationServiceFullPipeline:
    """Full pipeline tests using fake providers."""

    @pytest.mark.asyncio
    async def test_full_pipeline_yields_meta_text_audio_end(self, persona, poi_with_wiki):
        """Full pipeline: narrate() yields MetaEvent, TextEvent+AudioEvent pairs, EndEvent."""
        scripted_chunks = ["故宮。", " 始建於1925年。"]
        service = NarrationService(
            llm=FakeLlmProvider(scripted_chunks),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        assert len(events) >= 4, f"Expected at least 4 events, got {len(events)}: {events}"

        # First event must be MetaEvent
        assert isinstance(events[0], MetaEvent)
        # Last event must be EndEvent
        assert isinstance(events[-1], EndEvent)

        # Middle events are TextEvent and AudioEvent
        middle_events = events[1:-1]
        assert len(middle_events) > 0
        text_events = [e for e in middle_events if isinstance(e, TextEvent)]
        audio_events = [e for e in middle_events if isinstance(e, AudioEvent)]
        assert len(text_events) > 0, "Expected at least one TextEvent"
        assert len(audio_events) > 0, "Expected at least one AudioEvent"

    @pytest.mark.asyncio
    async def test_meta_event_cache_hit_false(self, persona, poi_with_wiki):
        """MetaEvent always has cache_hit=False (no cache integration yet)."""
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        meta = events[0]
        assert isinstance(meta, MetaEvent)
        assert meta.cache_hit is False

    @pytest.mark.asyncio
    async def test_meta_event_poi_id(self, persona, poi_with_wiki):
        """MetaEvent has correct poi_id."""
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        meta = events[0]
        assert isinstance(meta, MetaEvent)
        assert meta.poi_id == "osm:node:123"

    @pytest.mark.asyncio
    async def test_meta_event_confidence_high(self, persona, poi_with_wiki):
        """MetaEvent confidence=high when wiki extract >= 200 chars."""
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        meta = events[0]
        assert isinstance(meta, MetaEvent)
        assert meta.confidence == "high"

    @pytest.mark.asyncio
    async def test_meta_event_confidence_low(self, persona, poi_no_wiki):
        """MetaEvent confidence=low when no wiki."""
        service = NarrationService(
            llm=FakeLlmProvider(["某景點。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_no_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        meta = events[0]
        assert isinstance(meta, MetaEvent)
        assert meta.confidence == "low"


class TestNarrationServiceEventOrder:
    """Tests for correct event ordering."""

    @pytest.mark.asyncio
    async def test_events_in_correct_order_meta_pairs_end(self, persona, poi_with_wiki):
        """Events must follow: meta → (text + audio) pairs → end."""
        scripted_chunks = ["故宮。", " 始建於1925年。"]
        service = NarrationService(
            llm=FakeLlmProvider(scripted_chunks),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        # First must be MetaEvent
        first_type = type(events[0])
        assert isinstance(events[0], MetaEvent), f"First event must be MetaEvent, got {first_type}"
        # Last must be EndEvent
        last_type = type(events[-1])
        assert isinstance(events[-1], EndEvent), f"Last event must be EndEvent, got {last_type}"

        # Middle events must alternate text/audio in pairs
        middle = events[1:-1]
        assert len(middle) % 2 == 0, (
            f"Middle events must be even (text+audio pairs), got {len(middle)}"
        )
        for i in range(0, len(middle), 2):
            mid_type = type(middle[i])
            assert isinstance(middle[i], TextEvent), (
                f"Position {i} should be TextEvent, got {mid_type}"
            )
            mid_next_type = type(middle[i + 1])
            assert isinstance(middle[i + 1], AudioEvent), (
                f"Position {i + 1} should be AudioEvent, got {mid_next_type}"
            )

    @pytest.mark.asyncio
    async def test_text_and_audio_sentence_idx_match(self, persona, poi_with_wiki):
        """TextEvent and its corresponding AudioEvent must share the same sentence_idx."""
        scripted_chunks = ["故宮。", " 始建於1925年。"]
        service = NarrationService(
            llm=FakeLlmProvider(scripted_chunks),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        middle = events[1:-1]
        for i in range(0, len(middle), 2):
            text_evt = middle[i]
            audio_evt = middle[i + 1]
            assert isinstance(text_evt, TextEvent)
            assert isinstance(audio_evt, AudioEvent)
            t_idx = text_evt.sentence_idx
            a_idx = audio_evt.sentence_idx
            assert t_idx == a_idx, (
                f"sentence_idx mismatch: TextEvent={t_idx}, AudioEvent={a_idx}"
            )

    @pytest.mark.asyncio
    async def test_sentence_idx_increments(self, persona, poi_with_wiki):
        """sentence_idx must increment for each text/audio pair."""
        scripted_chunks = ["故宮。", " 始建於1925年。"]
        service = NarrationService(
            llm=FakeLlmProvider(scripted_chunks),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        text_events = [e for e in events if isinstance(e, TextEvent)]
        indices = [e.sentence_idx for e in text_events]
        assert indices == list(range(len(indices))), (
            f"sentence_idx must be 0,1,2,..., got {indices}"
        )


class TestNarrationServiceAudioEncoding:
    """Tests for audio base64 encoding correctness."""

    @pytest.mark.asyncio
    async def test_audio_chunk_b64_is_valid_base64(self, persona, poi_with_wiki):
        """AudioEvent.chunk_b64 must be valid base64-encoded non-empty bytes."""
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        audio_events = [e for e in events if isinstance(e, AudioEvent)]
        assert len(audio_events) > 0, "Expected at least one AudioEvent"

        for audio_evt in audio_events:
            # Must be decodable base64
            decoded = base64.b64decode(audio_evt.chunk_b64)
            # Must be non-empty bytes
            assert len(decoded) > 0, "Decoded audio bytes must be non-empty"

    @pytest.mark.asyncio
    async def test_audio_chunk_b64_decodes_to_fake_audio(self, persona, poi_with_wiki):
        """AudioEvent.chunk_b64 decodes to the FakeTtsProvider's silent audio bytes."""
        _SILENT_AUDIO = b"\x00" * 100

        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        audio_events = [e for e in events if isinstance(e, AudioEvent)]
        assert len(audio_events) > 0

        first_audio = audio_events[0]
        decoded = base64.b64decode(first_audio.chunk_b64)
        assert decoded == _SILENT_AUDIO, f"Expected silent audio bytes, got {decoded!r}"


class TestNarrationServiceEndEvent:
    """Tests for EndEvent."""

    @pytest.mark.asyncio
    async def test_end_event_is_last(self, persona, poi_with_wiki):
        """EndEvent must always be the last event yielded."""
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。", "始建於1925年。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        assert isinstance(events[-1], EndEvent)

    @pytest.mark.asyncio
    async def test_exactly_one_end_event(self, persona, poi_with_wiki):
        """There must be exactly one EndEvent."""
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。", "始建於1925年。"]),
            tts=FakeTtsProvider(),
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        end_events = [e for e in events if isinstance(e, EndEvent)]
        assert len(end_events) == 1, f"Expected exactly 1 EndEvent, got {len(end_events)}"


class TestNarrationServiceCache:
    """Tests for NarrationCache integration with NarrationService."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_audio_with_cache_hit_true(
        self, persona, poi_with_wiki, tmp_path
    ):
        """Cache hit: pre-populated cache causes MetaEvent(cache_hit=True) and single AudioEvent."""
        cache = NarrationCache(tmp_path)
        cached_audio = b"\xAB\xCD" * 50  # 100 bytes of fake cached audio
        cache_key = f"{poi_with_wiki.osm.id}|{persona.id}|zh-TW|medium"
        cache.put(cache_key, cached_audio, "pre-cached transcript")

        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
            cache=cache,
        )

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        # First event must be MetaEvent with cache_hit=True
        assert isinstance(events[0], MetaEvent)
        assert events[0].cache_hit is True

        # Should have a single AudioEvent with the cached audio
        audio_events = [e for e in events if isinstance(e, AudioEvent)]
        assert len(audio_events) == 1
        decoded = base64.b64decode(audio_events[0].chunk_b64)
        assert decoded == cached_audio

        # Last event must be EndEvent
        assert isinstance(events[-1], EndEvent)

        # No TextEvents on cache hit path
        text_events = [e for e in events if isinstance(e, TextEvent)]
        assert len(text_events) == 0

    @pytest.mark.asyncio
    async def test_cache_miss_populates_cache(self, persona, poi_with_wiki, tmp_path):
        """Cache miss: narrate() runs full pipeline and populates cache afterwards."""
        cache = NarrationCache(tmp_path)
        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
            cache=cache,
        )

        # Verify cache is empty before narration
        cache_key = f"{poi_with_wiki.osm.id}|{persona.id}|zh-TW|medium"
        assert cache.get(cache_key) is None

        events = []
        async for event in service.narrate(poi_with_wiki, persona, "zh-TW", "medium"):
            events.append(event)

        # After narration, cache should be populated
        cached = cache.get(cache_key)
        assert cached is not None
        cached_audio, _transcript = cached
        assert len(cached_audio) > 0

        # The MetaEvent should show cache_hit=False (it was a miss)
        assert isinstance(events[0], MetaEvent)
        assert events[0].cache_hit is False

    @pytest.mark.asyncio
    async def test_force_regenerate_bypasses_cache(self, persona, poi_with_wiki, tmp_path):
        """force_regenerate=True bypasses cache even when pre-populated."""
        cache = NarrationCache(tmp_path)
        cached_audio = b"\xFF" * 100  # distinctive fake cached audio
        cache_key = f"{poi_with_wiki.osm.id}|{persona.id}|zh-TW|medium"
        cache.put(cache_key, cached_audio, "old transcript")

        service = NarrationService(
            llm=FakeLlmProvider(["故宮。"]),
            tts=FakeTtsProvider(),
            cache=cache,
        )

        events = []
        async for event in service.narrate(
            poi_with_wiki, persona, "zh-TW", "medium", force_regenerate=True
        ):
            events.append(event)

        # MetaEvent should have cache_hit=False (bypass used)
        assert isinstance(events[0], MetaEvent)
        assert events[0].cache_hit is False

        # Pipeline ran, so TextEvents should be present
        text_events = [e for e in events if isinstance(e, TextEvent)]
        assert len(text_events) > 0
