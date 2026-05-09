"""Integration tests for POST /narration SSE endpoint."""

import base64
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.narration import get_narration_service, router
from tour_guide.services.narration_service import (
    AudioEvent,
    EndEvent,
    MetaEvent,
    TextEvent,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        if not block:
            continue
        event_type = None
        data = None
        for line in block.split("\n"):
            if line.startswith("event: "):
                event_type = line[len("event: "):]
            elif line.startswith("data: "):
                data = json.loads(line[len("data: "):])
        if event_type and data is not None:
            events.append({"type": event_type, **data})
    return events


# ---------------------------------------------------------------------------
# Fake NarrationService
# ---------------------------------------------------------------------------


class FakeNarrationService:
    async def narrate(self, poi, persona, lang, length, force_regenerate=False):
        yield MetaEvent(poi_id=poi.osm.id, cache_hit=False, confidence="high")
        yield TextEvent(chunk="故宮。", sentence_idx=0)
        yield AudioEvent(chunk_b64=base64.b64encode(b"\x00" * 100).decode(), sentence_idx=0)
        yield EndEvent()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Minimal FastAPI app with narration router and fake service injected."""
    application = FastAPI()
    application.include_router(router)

    fake_service = FakeNarrationService()
    application.dependency_overrides[get_narration_service] = lambda: fake_service

    return application


@pytest.fixture
def client(app):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNarrationAPIStreamOrder:
    """Test SSE event ordering from POST /narration."""

    def test_successful_stream_event_order(self, client):
        """First event is meta, middle has text/audio, last event is end."""
        response = client.post(
            "/narration",
            json={
                "poi_id": "osm:node:123",
                "persona": "history_uncle",
                "lang": "zh-TW",
                "length": "medium",
                "force_regenerate": False,
            },
        )
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        assert len(events) >= 4, f"Expected at least 4 events, got {len(events)}: {events}"

        # First event must be meta
        first_type = events[0]["type"]
        assert first_type == "meta", f"First event type must be 'meta', got {first_type}"

        # Last event must be end
        last_type = events[-1]["type"]
        assert last_type == "end", f"Last event type must be 'end', got {last_type}"

        # There must be text and audio events in between
        middle_types = {e["type"] for e in events[1:-1]}
        assert "text" in middle_types, "Expected 'text' events in response"
        assert "audio" in middle_types, "Expected 'audio' events in response"

    def test_meta_event_has_required_fields(self, client):
        """meta event data contains poi_id, cache_hit, confidence, estimated_duration_s."""
        response = client.post(
            "/narration",
            json={
                "poi_id": "osm:node:123",
                "persona": "history_uncle",
                "lang": "zh-TW",
                "length": "medium",
                "force_regenerate": False,
            },
        )
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        meta = next((e for e in events if e["type"] == "meta"), None)
        assert meta is not None, "Expected a meta event"

        assert "poi_id" in meta, "meta event must have poi_id"
        assert "cache_hit" in meta, "meta event must have cache_hit"
        assert "confidence" in meta, "meta event must have confidence"
        assert "estimated_duration_s" in meta, "meta event must have estimated_duration_s"

    def test_audio_event_has_chunk_b64_and_sentence_idx(self, client):
        """audio event data contains non-empty chunk_b64 and int sentence_idx."""
        response = client.post(
            "/narration",
            json={
                "poi_id": "osm:node:123",
                "persona": "history_uncle",
                "lang": "zh-TW",
                "length": "medium",
                "force_regenerate": False,
            },
        )
        assert response.status_code == 200

        events = parse_sse_events(response.text)
        audio = next((e for e in events if e["type"] == "audio"), None)
        assert audio is not None, "Expected at least one audio event"

        assert "chunk_b64" in audio, "audio event must have chunk_b64"
        assert isinstance(audio["chunk_b64"], str), "chunk_b64 must be a string"
        assert len(audio["chunk_b64"]) > 0, "chunk_b64 must be non-empty"

        assert "sentence_idx" in audio, "audio event must have sentence_idx"
        assert isinstance(audio["sentence_idx"], int), "sentence_idx must be an int"


class TestNarrationAPIValidation:
    """Test input validation for POST /narration."""

    def test_missing_poi_id_returns_422(self, client):
        """POST /narration without poi_id returns HTTP 422."""
        response = client.post("/narration", json={})
        assert response.status_code == 422
