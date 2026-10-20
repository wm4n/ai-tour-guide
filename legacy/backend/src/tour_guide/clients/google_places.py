"""Google Places API client: Protocol + Real + Fake implementations."""

from typing import Protocol

from tour_guide.models.poi import Place


class GooglePlacesClient(Protocol):
    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]: ...


class FakeGooglePlacesClient:
    """In-memory fake for tests and no-API-key environments."""

    def __init__(self, scripted_places: list[Place]) -> None:
        self._places = scripted_places

    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]:
        return self._places


_PRICE_LEVEL_MAP: dict[str, int] = {
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

_NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
_FIELD_MASK = (
    "places.id,places.displayName,places.location,"
    "places.rating,places.userRatingCount,places.priceLevel,"
    "places.types,places.formattedAddress"
)


class RealGooglePlacesClient:
    """Calls the Google Places API (New) Nearby Search."""

    def __init__(self, api_key: str) -> None:
        import httpx
        self._api_key = api_key
        self._client = httpx.AsyncClient()

    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]:
        import asyncio

        payload = {
            "includedTypes": ["restaurant", "cafe", "bakery"],
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": float(radius_m),
                }
            },
        }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
            "Content-Type": "application/json",
        }

        backoff = [1, 2, 4]
        last_exc: Exception | None = None

        for wait in [*backoff, None]:
            try:
                resp = await self._client.post(
                    _NEARBY_SEARCH_URL, json=payload, headers=headers
                )
                if resp.status_code == 429:
                    raise GooglePlacesRateLimitError()
                resp.raise_for_status()
                data = resp.json()
                return [_parse_place(p) for p in data.get("places", [])]
            except GooglePlacesRateLimitError:
                raise
            except Exception as e:
                last_exc = e
                if wait is not None:
                    await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]


class GooglePlacesRateLimitError(Exception):
    pass


def _parse_place(data: dict) -> Place:
    price_str = data.get("priceLevel", "")
    return Place(
        id=f"gplace:{data['id']}",
        name=data.get("displayName", {}).get("text", ""),
        lat=data["location"]["latitude"],
        lon=data["location"]["longitude"],
        rating=data.get("rating"),
        user_ratings_total=data.get("userRatingCount"),
        price_level=_PRICE_LEVEL_MAP.get(price_str),
        types=data.get("types", []),
        vicinity=data.get("formattedAddress", ""),
    )
