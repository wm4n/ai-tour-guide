import asyncio
import logging
from typing import Protocol

from buddy_host.places.geo import bounding_box
from buddy_host.places.merge import merge_wiki_hits
from buddy_host.places.models import BBox, Candidate
from buddy_host.places.wikipedia import WikiHit

logger = logging.getLogger(__name__)


class OverpassLike(Protocol):
    async def nearby(self, box: BBox) -> list[Candidate]: ...


class GeoSearchLike(Protocol):
    async def geosearch(self, lat: float, lon: float, radius_m: int) -> list[WikiHit]: ...


async def gather_candidates(
    overpass: OverpassLike, wiki: GeoSearchLike, lat: float, lon: float, radius_m: float
) -> list[Candidate]:
    """OSM 與維基座標搜尋同時查；其中一邊掛掉就只用另一邊（公共 Overpass 常常過載）。"""
    osm, hits = await asyncio.gather(
        overpass.nearby(bounding_box(lat, lon, radius_m)),
        wiki.geosearch(lat, lon, int(radius_m)),
        return_exceptions=True,
    )
    if isinstance(osm, BaseException) and isinstance(hits, BaseException):
        raise osm
    if isinstance(osm, BaseException):
        logger.warning("Overpass 失敗，只用維基座標搜尋：%s", osm)
        osm = []
    if isinstance(hits, BaseException):
        logger.warning("維基座標搜尋失敗，只用 OSM：%s", hits)
        hits = []
    return merge_wiki_hits(osm, hits)
