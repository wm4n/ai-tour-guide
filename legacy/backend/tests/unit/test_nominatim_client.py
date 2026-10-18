"""Tests for NominatimClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tour_guide.clients.nominatim import NominatimAddress, NominatimClient


class TestNominatimClientReverse:
    """Tests for NominatimClient.reverse()."""

    @pytest.fixture
    def mock_http(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_reverse_parses_suburb_and_city(self, mock_http):
        """reverse() parses suburb and city from Nominatim response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "address": {"suburb": "大安區", "city": "台北市"}
        }
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(25.04, 121.53)

        assert result is not None
        assert result.suburb == "大安區"
        assert result.city == "台北市"

    @pytest.mark.asyncio
    async def test_reverse_uses_borough_as_suburb_fallback(self, mock_http):
        """reverse() falls back to borough when suburb is absent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "address": {"borough": "Brooklyn", "city": "New York City"}
        }
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(40.65, -73.95)

        assert result is not None
        assert result.suburb == "Brooklyn"
        assert result.city == "New York City"

    @pytest.mark.asyncio
    async def test_reverse_uses_town_as_city_fallback(self, mock_http):
        """reverse() falls back to town when city is absent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "address": {"suburb": "West End", "town": "Small Town"}
        }
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(51.5, -1.8)

        assert result is not None
        assert result.city == "Small Town"

    @pytest.mark.asyncio
    async def test_reverse_returns_none_on_http_error(self, mock_http):
        """reverse() returns None when HTTP call raises an exception."""
        mock_http.get.side_effect = Exception("Network error")

        client = NominatimClient(client=mock_http)
        result = await client.reverse(25.04, 121.53)

        assert result is None

    @pytest.mark.asyncio
    async def test_reverse_returns_none_on_non_200(self, mock_http):
        """reverse() returns None when status code is not 200."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(25.04, 121.53)

        assert result is None
