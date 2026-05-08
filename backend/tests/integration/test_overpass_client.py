"""Integration tests for OverpassClient using respx to mock HTTP calls."""

import httpx
import pytest
import respx

from tour_guide.clients.overpass import OverpassClient, OverpassRateLimitError
from tour_guide.models.poi import BBox, OsmNode, TagFilter

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

SAMPLE_BBOX = BBox(min_lat=25.0, min_lon=121.5, max_lat=25.2, max_lon=121.6)
SAMPLE_TAGS = [TagFilter(key="tourism")]


@pytest.fixture()
def client():
    return OverpassClient(client=httpx.AsyncClient())


class TestOverpassClientQuery:
    """Tests for OverpassClient.query()."""

    @respx.mock
    async def test_successful_query_returns_osm_node_list(self, client):
        """Successful response returns list of OsmNode with correct fields."""
        respx.post(OVERPASS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "elements": [
                        {
                            "type": "node",
                            "id": 12345,
                            "lat": 25.1023,
                            "lon": 121.5482,
                            "tags": {
                                "name": "故宮博物院",
                                "tourism": "museum",
                            },
                        }
                    ]
                },
            )
        )

        results = await client.query(SAMPLE_BBOX, SAMPLE_TAGS)

        assert len(results) == 1
        node = results[0]
        assert isinstance(node, OsmNode)
        assert node.id == "osm:node:12345"
        assert node.lat == 25.1023
        assert node.lon == 121.5482
        assert node.tags == {"name": "故宮博物院", "tourism": "museum"}

    @respx.mock
    async def test_503_retry_succeeds_on_second_attempt(self, client):
        """503 on first attempt triggers retry; second attempt succeeds."""
        respx.post(OVERPASS_URL).mock(
            side_effect=[
                httpx.Response(503),
                httpx.Response(
                    200,
                    json={
                        "elements": [
                            {
                                "type": "node",
                                "id": 99999,
                                "lat": 25.05,
                                "lon": 121.55,
                                "tags": {"name": "測試地點"},
                            }
                        ]
                    },
                ),
            ]
        )

        results = await client.query(SAMPLE_BBOX, SAMPLE_TAGS)

        assert len(results) == 1
        assert results[0].id == "osm:node:99999"

    @respx.mock
    async def test_429_raises_overpass_rate_limit_error(self, client):
        """429 response raises OverpassRateLimitError with retry_after_s."""
        respx.post(OVERPASS_URL).mock(
            return_value=httpx.Response(429)
        )

        with pytest.raises(OverpassRateLimitError) as exc_info:
            await client.query(SAMPLE_BBOX, SAMPLE_TAGS)

        assert exc_info.value.retry_after_s > 0
