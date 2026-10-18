"""Tests for WikipediaClient.search() method."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tour_guide.clients.wikipedia import WikipediaClient


class TestWikipediaClientSearch:
    """Tests for WikipediaClient.search()."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_search_returns_first_title_on_match(self, mock_client):
        """search() returns the first title from opensearch results."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            "故宮博物院",
            ["國立故宮博物院", "故宮博物院 (北京)"],
            ["", ""],
            ["https://zh.wikipedia.org/...", "https://zh.wikipedia.org/..."],
        ]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        result = await client.search("故宮博物院", "zh-TW")

        assert result == "國立故宮博物院"

    @pytest.mark.asyncio
    async def test_search_returns_none_when_no_results(self, mock_client):
        """search() returns None when opensearch returns no titles."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["xyz", [], [], []]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        result = await client.search("NoSuchPlace", "zh-TW")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_maps_zh_tw_to_zh_subdomain(self, mock_client):
        """search() maps zh-TW to zh subdomain."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["q", ["Title"], [""], [""]]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        await client.search("query", "zh-TW")

        call_url = mock_client.get.call_args[0][0]
        assert "zh.wikipedia.org" in call_url

    @pytest.mark.asyncio
    async def test_search_uses_opensearch_action(self, mock_client):
        """search() calls the opensearch API action."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["q", [], [], []]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        await client.search("query", "en")

        params = mock_client.get.call_args[1]["params"]
        assert params["action"] == "opensearch"
        assert params["search"] == "query"
        assert params["limit"] == "1"
