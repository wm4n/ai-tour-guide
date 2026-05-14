"""Integration tests for the app factory and full DI wiring."""

import pytest
from fastapi.testclient import TestClient

from tour_guide.config import AppConfig
from tour_guide.main import create_app


class TestAppFactory:
    """Tests for create_app() factory function."""

    @pytest.fixture
    def app(self, monkeypatch):
        """Create app with test API key."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        config = AppConfig()
        return create_app(config)

    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return TestClient(app)

    def test_app_has_all_routes(self, app):
        """App registers all 3 expected routes."""
        routes = {route.path for route in app.routes}
        assert "/health" in routes
        assert "/poi/nearby" in routes
        assert "/narration" in routes

    def test_health_route_works(self, client):
        """GET /health returns 200 with ok status."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_dependency_overrides_set(self, app):
        """Dependency overrides are configured for poi and narration services."""
        from tour_guide.api import narration, poi

        assert poi.get_poi_service in app.dependency_overrides
        assert narration.get_narration_service in app.dependency_overrides


class TestApiKeyMiddleware:
    """Tests for X-Api-Key middleware."""

    @pytest.fixture
    def app_no_key(self, monkeypatch):
        """Create app with empty API_KEY (dev mode — bypass auth)."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("API_KEY", "")
        config = AppConfig()
        return create_app(config)

    @pytest.fixture
    def app_with_key(self, monkeypatch):
        """Create app with a configured API_KEY."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        monkeypatch.setenv("API_KEY", "secret-key-123")
        config = AppConfig()
        return create_app(config)

    def test_empty_api_key_bypasses_auth(self, app_no_key):
        """When API_KEY is empty, all requests are allowed without header."""
        client = TestClient(app_no_key)
        response = client.get("/health")
        assert response.status_code == 200

    def test_correct_api_key_is_accepted(self, app_with_key):
        """When API_KEY is set, correct X-Api-Key header is accepted."""
        client = TestClient(app_with_key)
        response = client.get("/health", headers={"X-Api-Key": "secret-key-123"})
        assert response.status_code == 200

    def test_wrong_api_key_returns_401(self, app_with_key):
        """When API_KEY is set, wrong X-Api-Key header returns 401."""
        client = TestClient(app_with_key)
        response = client.get("/health", headers={"X-Api-Key": "wrong-key"})
        assert response.status_code == 401

    def test_missing_api_key_header_returns_401(self, app_with_key):
        """When API_KEY is set, missing X-Api-Key header returns 401."""
        client = TestClient(app_with_key)
        response = client.get("/health")
        assert response.status_code == 401
