"""Tests for GooglePlacesClient: FakeGooglePlacesClient behaviour."""

import pytest

from tour_guide.clients.google_places import FakeGooglePlacesClient
from tour_guide.models.poi import Place


@pytest.fixture()
def sample_places():
    return [
        Place(
            id="gplace:ChIJ001",
            name="鼎泰豐",
            lat=25.033,
            lon=121.564,
            rating=4.6,
            user_ratings_total=328,
            price_level=2,
            types=["restaurant", "food"],
            vicinity="信義區松高路12號",
        ),
        Place(
            id="gplace:ChIJ002",
            name="阜杭豆漿",
            lat=25.045,
            lon=121.530,
            rating=4.8,
            user_ratings_total=1200,
            price_level=1,
            types=["restaurant", "cafe"],
            vicinity="忠孝東路一段108號",
        ),
    ]


class TestFakeGooglePlacesClient:
    async def test_returns_scripted_places(self, sample_places):
        """FakeGooglePlacesClient returns the scripted list unchanged."""
        client = FakeGooglePlacesClient(scripted_places=sample_places)
        result = await client.nearby_restaurants(25.033, 121.564, 500)
        assert result == sample_places

    async def test_empty_scripted_places(self):
        """FakeGooglePlacesClient with empty list returns empty list."""
        client = FakeGooglePlacesClient(scripted_places=[])
        result = await client.nearby_restaurants(25.0, 121.0, 500)
        assert result == []
