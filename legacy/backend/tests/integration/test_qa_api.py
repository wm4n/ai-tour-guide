"""Integration tests for POST /qa SSE endpoint."""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.qa import get_persona_registry, get_qa_service, router
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.providers.fakes import FakeLlmProvider, FakeTtsProvider
from tour_guide.providers.stt import FakeSttProvider
from tour_guide.services.qa_service import QAService


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


_FAKE_REGISTRY: dict = {
    "history_uncle": PersonaConfig(
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
    ),
}


@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router)
    qa_svc = QAService(
        stt=FakeSttProvider("這裡有多少文物？"),
        llm=FakeLlmProvider(["故宮有約七十萬件文物。"]),
        tts=FakeTtsProvider(),
    )
    application.dependency_overrides[get_qa_service] = lambda: qa_svc
    application.dependency_overrides[get_persona_registry] = lambda: _FAKE_REGISTRY
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


def _post_qa(client, persona="history_uncle", poi_id="osm:1"):
    audio_bytes = b"\x00" * 100
    context = json.dumps({
        "current_poi_id": poi_id,
        "persona": persona,
        "lang": "zh-TW",
        "narration_so_far": "故宮是台灣最重要的博物館。",
    })
    return client.post(
        "/qa",
        files={"audio": ("recording.wav", audio_bytes, "audio/wav")},
        data={"context": context},
    )


class TestQAAPIStreamOrder:
    def test_first_event_is_transcript(self, client):
        response = _post_qa(client)
        assert response.status_code == 200
        events = parse_sse_events(response.text)
        assert events[0]["type"] == "transcript"
        assert "text" in events[0]

    def test_last_event_is_end(self, client):
        response = _post_qa(client)
        events = parse_sse_events(response.text)
        assert events[-1]["type"] == "end"

    def test_audio_event_has_chunk_b64(self, client):
        response = _post_qa(client)
        events = parse_sse_events(response.text)
        audio = next((e for e in events if e["type"] == "audio"), None)
        assert audio is not None
        assert len(audio["chunk_b64"]) > 0


class TestQAAPIValidation:
    def test_unknown_persona_returns_400(self, client):
        audio_bytes = b"\x00" * 100
        context = json.dumps({
            "current_poi_id": "osm:1",
            "persona": "unknown_persona",
            "lang": "zh-TW",
            "narration_so_far": "",
        })
        response = client.post(
            "/qa",
            files={"audio": ("recording.wav", audio_bytes, "audio/wav")},
            data={"context": context},
        )
        assert response.status_code == 400

    def test_missing_audio_returns_422(self, client):
        context = json.dumps({"persona": "history_uncle", "lang": "zh-TW", "narration_so_far": ""})
        response = client.post("/qa", data={"context": context})
        assert response.status_code == 422
