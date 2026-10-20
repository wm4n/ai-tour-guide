"""Nominatim reverse geocoding client for OSM address lookup."""

from dataclasses import dataclass

import httpx


@dataclass
class NominatimAddress:
    suburb: str | None
    city_district: str | None
    city: str | None
    town: str | None
    village: str | None


class NominatimClient:
    BASE_URL = "https://nominatim.openstreetmap.org/reverse"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": "ai-tour-guide/1.0"}
        )

    async def reverse(self, lat: float, lon: float) -> NominatimAddress | None:
        """Reverse geocode lat/lon to an address.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            NominatimAddress with suburb and city fields, or None on any error.
        """
        try:
            resp = await self._client.get(
                self.BASE_URL,
                params={"lat": lat, "lon": lon, "format": "json", "zoom": 14},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            address = data.get("address", {})
            return NominatimAddress(
                suburb=address.get("suburb") or address.get("borough"),
                city_district=address.get("city_district"),
                city=address.get("city") or address.get("town") or address.get("village"),
                town=address.get("town"),
                village=address.get("village"),
            )
        except Exception:
            return None
