"""Integration tests for POI API endpoint."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tour_guide.api.poi import get_poi_service, router
from tour_guide.clients.overpass import OverpassRateLimitError
from tour_guide.models.poi import POI, WikiArticle

# ---------------------------------------------------------------------------
# Fake POIService for testing
# ---------------------------------------------------------------------------


class FakePOIService:
    """Fake POIService for dependency injection in tests."""

    def __init__(self, pois=None, error=None):
        """Initialize with optional fixed response or error.

        Args:
            pois: List[POI] to return, or None
            error: Exception to raise, or None
        """
        self._pois = pois or []
        self._error = error

    async def nearby(self, lat, lon, radius, persona, lang):
        """Return fixed POIs or raise error."""
        if self._error:
            raise self._error
        return self._pois


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_poi():
    """Create a sample POI."""
    return POI(
        id="osm:node:12345",
        name="故宮博物院",
        lat=25.1023,
        lon=121.5482,
        tags={"tourism": "museum", "name": "故宮博物院"},
        wiki=WikiArticle(
            title="國立故宮博物院",
            extract="National Palace Museum Taipei Taiwan " * 7,
            url="https://zh.wikipedia.org/wiki/國立故宮博物院",
            lang="zh",
        ),
        distance_m=100.0,
        confidence="high",
    )


@pytest.fixture
def app():
    """Create a minimal FastAPI app with POI router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Valid request returns 200 with pois list
# ---------------------------------------------------------------------------


class TestPOINearbyAPI:
    """Tests for POI nearby API endpoint."""

    def test_valid_request_returns_200_with_pois(self, app, client, sample_poi):
        """GET /poi/nearby with valid params returns 200 with POI list."""
        fake_service = FakePOIService(pois=[sample_poi])

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle"
        )

        assert response.status_code == 200
        data = response.json()
        assert "pois" in data
        assert "queried_at" in data
        assert len(data["pois"]) == 1
        poi = data["pois"][0]
        assert poi["id"] == sample_poi.id
        assert poi["name"] == sample_poi.name
        assert poi["lat"] == sample_poi.lat
        assert poi["lon"] == sample_poi.lon
        assert poi["distance_m"] == sample_poi.distance_m
        assert poi["confidence"] == sample_poi.confidence
        assert poi["wiki"] is not None
        assert poi["wiki"]["title"] == sample_poi.wiki.title

    # ---------------------------------------------------------------------------
    # Test 2: Invalid coordinates return 422
    # ---------------------------------------------------------------------------

    def test_invalid_lat_returns_422(self, app, client):
        """GET /poi/nearby with invalid lat (999) returns 422."""
        fake_service = FakePOIService(pois=[])

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=999&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle"
        )

        assert response.status_code == 422  # FastAPI validation error

    def test_invalid_lon_returns_422(self, app, client):
        """GET /poi/nearby with invalid lon (999) returns 422."""
        fake_service = FakePOIService(pois=[])

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=25.1023&lon=999&radius=500&lang=zh-TW&persona=history_uncle"
        )

        assert response.status_code == 422  # FastAPI validation error

    # ---------------------------------------------------------------------------
    # Test 3: Upstream 429 returns 429 with Retry-After header
    # ---------------------------------------------------------------------------

    def test_upstream_429_returns_429_with_retry_after(self, app, client):
        """GET /poi/nearby when service raises OverpassRateLimitError returns 429."""
        error = OverpassRateLimitError(retry_after_s=30)
        fake_service = FakePOIService(error=error)

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle"
        )

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert response.headers["Retry-After"] == "30"

    # ---------------------------------------------------------------------------
    # Test 4: Upstream 503 returns 503
    # ---------------------------------------------------------------------------

    def test_upstream_exception_returns_503(self, app, client):
        """GET /poi/nearby when service raises generic Exception returns 503."""
        error = Exception("Overpass unavailable")
        fake_service = FakePOIService(error=error)

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle"
        )

        assert response.status_code == 503
