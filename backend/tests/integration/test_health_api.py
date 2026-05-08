"""Integration tests for Health API endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.health import router


class TestHealthAPI:
    """Tests for Health API endpoint."""

    @pytest.fixture
    def app(self):
        """Create a minimal FastAPI app with health router."""
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    def test_health_returns_200(self, client):
        """GET /health returns HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        """Health response has correct structure."""
        response = client.get("/health")
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "uptime_s" in data
        assert isinstance(data["uptime_s"], int)
        assert data["uptime_s"] >= 0
