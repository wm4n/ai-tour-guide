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
