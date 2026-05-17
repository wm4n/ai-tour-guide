"""Tests for SKIP path in narration endpoint."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI
from tour_guide.api import narration as narration_module
from tour_guide.api.narration import NarrationRequest, POICandidate
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle


def _make_persona():
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


def _make_app(selector_returns=None):
    app = FastAPI()
    app.include_router(narration_module.router)

    fake_selector = MagicMock()
    fake_selector.select = AsyncMock(return_value=selector_returns)

    fake_narration = MagicMock()

    app.dependency_overrides[narration_module.get_poi_selector_service] = lambda: fake_selector
    app.dependency_overrides[narration_module.get_narration_service] = lambda: fake_narration
    app.dependency_overrides[narration_module.get_persona_registry] = lambda: {
        "history_uncle": _make_persona()
    }
    return app


def test_skip_returns_skip_sse_event():
    app = _make_app(selector_returns=None)
    client = TestClient(app)
    payload = {
        "candidates": [
            {"poi_id": "node/1", "poi_name": "地圖", "distance_m": 30}
        ],
        "persona": "history_uncle",
        "lang": "zh-TW",
    }
    response = client.post("/narration", json=payload, headers={"Accept": "text/event-stream"})
    assert response.status_code == 200
    body = response.text
    assert "event: skip" in body
    assert "min_displacement_m" in body
