"""Tests for WikipediaResolver fallback chain."""

import pytest
from unittest.mock import AsyncMock

from tour_guide.clients.nominatim import NominatimAddress, NominatimClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import WikiArticle
from tour_guide.services.wikipedia_resolver import WikipediaResolver


@pytest.fixture
def mock_wikipedia():
    return AsyncMock(spec=WikipediaClient)


@pytest.fixture
def mock_nominatim():
    return AsyncMock(spec=NominatimClient)


@pytest.fixture
def resolver(mock_wikipedia, mock_nominatim):
    return WikipediaResolver(wikipedia=mock_wikipedia, nominatim=mock_nominatim)


_SAMPLE_ARTICLE = WikiArticle(title="故宮", extract="故宮的歷史...", url="", lang="zh-TW")


class TestWikipediaResolverDirectSearch:
    @pytest.mark.asyncio
    async def test_direct_name_match_returns_article(self, resolver, mock_wikipedia, mock_nominatim):
        """If direct poi_name search succeeds, return the article without calling Nominatim."""
        mock_wikipedia.search.return_value = "國立故宮博物院"
        mock_wikipedia.summary.return_value = _SAMPLE_ARTICLE

        result = await resolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")

        assert result == _SAMPLE_ARTICLE
        mock_nominatim.reverse.assert_not_called()

    @pytest.mark.asyncio
    async def test_direct_search_with_no_title_moves_to_next_level(self, resolver, mock_wikipedia, mock_nominatim):
        """If poi_name search returns no title, call Nominatim and continue."""
        mock_wikipedia.search.return_value = None
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb=None, city_district=None, city=None, town=None, village=None
        )

        result = await resolver.resolve("Unknown Place", 25.04, 121.56, "zh-TW")

        assert result is None
        mock_nominatim.reverse.assert_called_once()


class TestWikipediaResolverSuburbFallback:
    @pytest.mark.asyncio
    async def test_suburb_fallback_used_when_direct_fails(self, resolver, mock_wikipedia, mock_nominatim):
        """Falls back to 'poi_name，suburb' when direct search fails."""
        mock_wikipedia.search.side_effect = [None, "故宮博物院"]
        mock_wikipedia.summary.return_value = _SAMPLE_ARTICLE
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb="大安區", city_district=None, city="台北市", town=None, village=None
        )

        result = await resolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")

        assert result == _SAMPLE_ARTICLE
        assert mock_wikipedia.search.call_count == 2
        second_query = mock_wikipedia.search.call_args_list[1][0][0]
        assert "大安區" in second_query

    @pytest.mark.asyncio
    async def test_suburb_skipped_when_none(self, resolver, mock_wikipedia, mock_nominatim):
        """If suburb is None, skip suburb search and try city."""
        mock_wikipedia.search.side_effect = [None, "故宮，台北市"]
        mock_wikipedia.summary.return_value = _SAMPLE_ARTICLE
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb=None, city_district=None, city="台北市", town=None, village=None
        )

        result = await resolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")

        assert result == _SAMPLE_ARTICLE
        second_query = mock_wikipedia.search.call_args_list[1][0][0]
        assert "台北市" in second_query


class TestWikipediaResolverCityFallback:
    @pytest.mark.asyncio
    async def test_city_fallback_used_when_suburb_fails(self, resolver, mock_wikipedia, mock_nominatim):
        """Falls back to 'poi_name，city' when suburb search also fails."""
        mock_wikipedia.search.side_effect = [None, None, "Brooklyn Bridge"]
        mock_wikipedia.summary.return_value = WikiArticle(
            title="Brooklyn Bridge", extract="...", url="", lang="en"
        )
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb="Brooklyn", city_district=None, city="New York City", town=None, village=None
        )

        result = await resolver.resolve("Brooklyn Bridge", 40.71, -73.99, "en")

        assert result is not None
        assert mock_wikipedia.search.call_count == 3
        city_query = mock_wikipedia.search.call_args_list[2][0][0]
        assert "New York City" in city_query


class TestWikipediaResolverAllFail:
    @pytest.mark.asyncio
    async def test_returns_none_when_all_levels_fail(self, resolver, mock_wikipedia, mock_nominatim):
        """Returns None when all fallback levels fail."""
        mock_wikipedia.search.return_value = None
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb="大安區", city_district=None, city="台北市", town=None, village=None
        )

        result = await resolver.resolve("Unknown Place", 25.04, 121.56, "zh-TW")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_nominatim_fails(self, resolver, mock_wikipedia, mock_nominatim):
        """Returns None when Nominatim returns None (network error)."""
        mock_wikipedia.search.return_value = None
        mock_nominatim.reverse.return_value = None

        result = await resolver.resolve("Some Place", 25.04, 121.56, "zh-TW")

        assert result is None
        assert mock_wikipedia.search.call_count == 1
