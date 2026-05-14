"""Overpass API client for querying OpenStreetMap data."""

import asyncio
import logging
import time

import httpx

from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event
from tour_guide.models.poi import BBox, OsmNode, TagFilter

logger = logging.getLogger(__name__)


class OverpassRateLimitError(Exception):
    def __init__(self, retry_after_s: int = 60):
        self.retry_after_s = retry_after_s
        super().__init__(f"Overpass rate limit. Retry after {retry_after_s}s")


class OverpassClient:
    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient()

    def _build_query(self, bbox: BBox, tags: list[TagFilter]) -> str:
        conditions = "\n".join(
            f'  node["{t.key}"]({bbox.min_lat},{bbox.min_lon},{bbox.max_lat},{bbox.max_lon});'
            for t in tags
        )
        return f"[out:json];\n(\n{conditions}\n);\nout body;"

    async def query(self, bbox: BBox, tags: list[TagFilter]) -> list[OsmNode]:
        query = self._build_query(bbox, tags)
        backoff = [1, 2, 4]
        last_exc: Exception | None = None
        start = time.monotonic()
        log_event(logger, LogEvents.OVERPASS_REQUEST, level="debug", tag_count=len(tags))

        for attempt, wait in enumerate([*backoff, None], start=1):
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
                nodes = [
                    OsmNode(
                        id=f"osm:{el['type']}:{el['id']}",
                        lat=el["lat"],
                        lon=el["lon"],
                        tags=el.get("tags", {}),
                    )
                    for el in data.get("elements", [])
                ]
                elapsed_ms = int((time.monotonic() - start) * 1000)
                log_event(
                    logger, LogEvents.OVERPASS_RESPONSE,
                    level="debug", node_count=len(nodes), duration_ms=elapsed_ms,
                )
                return nodes
            except OverpassRateLimitError:
                raise
            except Exception as e:
                last_exc = e
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                log_event(
                    logger, LogEvents.OVERPASS_RETRY,
                    level="warning", attempt=attempt, status_code=status_code,
                )
                if wait is not None:
                    await asyncio.sleep(wait)

        raise last_exc
