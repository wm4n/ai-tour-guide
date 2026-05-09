"""Integration tests for WikipediaClient using respx to mock HTTP calls."""

import httpx
import pytest
import respx

from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import WikiArticle


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
