"""Integration tests for WikipediaClient using respx to mock HTTP calls."""

import httpx
import pytest
import respx

from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import OsmNode, WikiArticle


@pytest.fixture()
def client():
    return WikipediaClient(client=httpx.AsyncClient())


class TestWikipediaClientSummary:
    """Tests for WikipediaClient.summary()."""

    @respx.mock
    async def test_known_title_returns_wiki_article(self, client):
        """Known title returns WikiArticle with correct fields."""
        respx.get("https://zh.wikipedia.org/api/rest_v1/page/summary/故宮博物院").mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "standard",
                    "title": "故宮博物院",
                    "extract": "國立故宮博物院是...",
                    "content_urls": {
                        "desktop": {"page": "https://zh.wikipedia.org/wiki/故宮博物院"}
                    },
                },
            )
        )

        result = await client.summary("故宮博物院", "zh")

        assert result is not None
        assert isinstance(result, WikiArticle)
        assert result.title == "故宮博物院"
        assert result.extract == "國立故宮博物院是..."
        assert result.url == "https://zh.wikipedia.org/wiki/故宮博物院"
        assert result.lang == "zh"

    @respx.mock
    async def test_unknown_title_returns_none(self, client):
        """404 response returns None."""
        respx.get("https://zh.wikipedia.org/api/rest_v1/page/summary/不存在的頁面").mock(
            return_value=httpx.Response(404)
        )

        result = await client.summary("不存在的頁面", "zh")

        assert result is None

    @respx.mock
    async def test_disambiguation_returns_none(self, client):
        """Disambiguation page returns None."""
        respx.get("https://zh.wikipedia.org/api/rest_v1/page/summary/台灣").mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "disambiguation",
                    "title": "台灣",
                    "extract": "台灣可能指:",
                    "content_urls": {"desktop": {"page": "https://zh.wikipedia.org/wiki/台灣"}},
                },
            )
        )

        result = await client.summary("台灣", "zh")

        assert result is None

    @respx.mock
    async def test_zh_tw_lang_mapped_to_zh_subdomain(self, client):
        """zh-TW is normalized to zh for the Wikipedia subdomain request."""
        respx.get("https://zh.wikipedia.org/api/rest_v1/page/summary/故宮").mock(
            return_value=httpx.Response(
                200,
                json={
                    "type": "standard",
                    "title": "故宮",
                    "extract": "故宮...",
                    "content_urls": {"desktop": {"page": "https://zh.wikipedia.org/wiki/故宮"}},
                },
            )
        )

        result = await client.summary("故宮", "zh-TW")

        assert result is not None
        assert result.lang == "zh-TW"  # original lang preserved in model


class TestWikipediaClientGeosearch:
    """Tests for WikipediaClient.geosearch()."""

    @respx.mock
    async def test_geosearch_returns_osm_nodes(self, client):
        """Successful geosearch returns OsmNode list with tourism and wikipedia tags."""
        respx.get("https://en.wikipedia.org/w/api.php").mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": {
                        "geosearch": [
                            {
                                "pageid": 12345,
                                "ns": 0,
                                "title": "Golden Gate Bridge",
                                "lat": 37.8199,
                                "lon": -122.4783,
                                "dist": 123.4,
                                "primary": "",
                            }
                        ]
                    }
                },
            )
        )

        nodes = await client.geosearch(37.8199, -122.4783, 500, "en")

        assert len(nodes) == 1
        node = nodes[0]
        assert isinstance(node, OsmNode)
        assert node.id == "wiki:12345"
        assert node.lat == 37.8199
        assert node.lon == -122.4783
        assert node.tags["tourism"] == "attraction"
        assert node.tags["wikipedia"] == "en:Golden Gate Bridge"

    @respx.mock
    async def test_geosearch_empty_results_returns_empty_list(self, client):
        """Empty geosearch response returns empty list."""
        respx.get("https://en.wikipedia.org/w/api.php").mock(
            return_value=httpx.Response(
                200,
                json={"query": {"geosearch": []}},
            )
        )

        nodes = await client.geosearch(37.8199, -122.4783, 500, "en")

        assert nodes == []

    @respx.mock
    async def test_geosearch_zh_tw_uses_zh_subdomain(self, client):
        """zh-TW lang maps to zh Wikipedia subdomain with zh-prefixed tags."""
        respx.get("https://zh.wikipedia.org/w/api.php").mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": {
                        "geosearch": [
                            {
                                "pageid": 99999,
                                "ns": 0,
                                "title": "故宮",
                                "lat": 25.1023,
                                "lon": 121.5482,
                                "dist": 0.0,
                                "primary": "",
                            }
                        ]
                    }
                },
            )
        )

        nodes = await client.geosearch(25.1023, 121.5482, 500, "zh-TW")

        assert len(nodes) == 1
        assert nodes[0].tags["wikipedia"] == "zh:故宮"
