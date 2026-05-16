"""WikipediaResolver: multi-level fallback chain for Wikipedia article lookup."""

from tour_guide.clients.nominatim import NominatimClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import WikiArticle


class WikipediaResolver:
    """Resolve a POI name to a Wikipedia article via a 4-level fallback chain.

    Fallback order:
    1. Direct search by poi_name
    2. Search by "poi_name，suburb" (via Nominatim reverse geocoding)
    3. Search by "poi_name，city" (via Nominatim reverse geocoding)
    4. Return None — caller handles the no-data case
    """

    def __init__(self, wikipedia: WikipediaClient, nominatim: NominatimClient) -> None:
        self._wikipedia = wikipedia
        self._nominatim = nominatim

    async def resolve(
        self, poi_name: str, lat: float, lon: float, lang: str
    ) -> WikiArticle | None:
        """Find a Wikipedia article for the given POI, using progressively broader search terms.

        Args:
            poi_name: The landmark name to look up.
            lat: Latitude of the POI (used for reverse geocoding).
            lon: Longitude of the POI (used for reverse geocoding).
            lang: Language code (e.g. "zh-TW", "en").

        Returns:
            WikiArticle if any level finds a result, otherwise None.
        """
        # Level 1: direct POI name
        article = await self._fetch(poi_name, lang)
        if article:
            return article

        # Reverse geocode once for levels 2 and 3
        address = await self._nominatim.reverse(lat, lon)
        if address is None:
            return None

        suburb = address.suburb or address.city_district
        city = address.city or address.town or address.village

        # Level 2: poi_name + suburb/district
        if suburb:
            article = await self._fetch(f"{poi_name}，{suburb}", lang)
            if article:
                return article

        # Level 3: poi_name + city
        if city:
            article = await self._fetch(f"{poi_name}，{city}", lang)
            if article:
                return article

        return None

    async def _fetch(self, query: str, lang: str) -> WikiArticle | None:
        title = await self._wikipedia.search(query, lang)
        if not title:
            return None
        return await self._wikipedia.summary(title, lang)
