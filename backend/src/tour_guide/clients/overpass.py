"""Overpass API client for querying OpenStreetMap data."""

import asyncio

import httpx

from tour_guide.models.poi import BBox, OsmNode, TagFilter


class OverpassRateLimitError(Exception):
    def __init__(self, retry_after_s: int = 60):
        self.retry_after_s = retry_after_s
        super().__init__(f"Overpass rate limit. Retry after {retry_after_s}s")


class OverpassClient:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient()

    def _build_query(self, bbox: BBox, tags: list[TagFilter]) -> str:
        """Build Overpass QL query for nodes in bbox with any of the given tags."""
        conditions = "\n".join(
            f'  node["{t.key}"]({bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon});'
            for t in tags
        )
        return f"[out:json];\n(\n{conditions}\n);\nout body;"

    async def query(self, bbox: BBox, tags: list[TagFilter]) -> list[OsmNode]:
        query = self._build_query(bbox, tags)
        backoff = [1, 2, 4]
        last_exc: Exception | None = None

        for wait in [*backoff, None]:
            try:
                resp = await self._client.post(
                    self.OVERPASS_URL,
                    data={"data": query},
                )
                if resp.status_code == 429:
                    raise OverpassRateLimitError()
                if resp.status_code == 503:
                    raise httpx.HTTPStatusError("503", request=resp.request, response=resp)
                resp.raise_for_status()
                data = resp.json()
                return [
                    OsmNode(
                        id=f"osm:{el['type']}:{el['id']}",
                        lat=el["lat"],
                        lon=el["lon"],
                        tags=el.get("tags", {}),
                    )
                    for el in data.get("elements", [])
                ]
            except OverpassRateLimitError:
                raise
            except Exception as e:
                last_exc = e
                if wait is not None:
                    await asyncio.sleep(wait)

        raise last_exc
