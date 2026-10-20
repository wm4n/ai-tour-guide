"""Overpass（OpenStreetMap）：找出附近的景點、古蹟、廟宇，以及有故事的老店。"""

import httpx2

from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp
from buddy_host.places.models import BBox, Candidate

# 公共 Overpass 常常過載（官方站會回 502 "at capacity"），依序換站
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# 有 name 且帶這些標記的 OSM 物件（node／way／relation）
_FILTERS = (
    '["tourism"]',
    '["historic"]',
    '["amenity"="place_of_worship"]',
    '["heritage"]',
    '["start_date"]',
    '["wikipedia"]',
    '["wikidata"]',
)
_ZH_PREFIXES = ("zh:", "zh-tw:", "zh-hant:")


def build_query(box: BBox) -> str:
    area = f"({box.min_lat},{box.min_lon},{box.max_lat},{box.max_lon})"
    lines = "\n".join(f'  nwr["name"]{f}{area};' for f in _FILTERS)
    return f"[out:json][timeout:25];\n(\n{lines}\n);\nout center tags;"


def _wiki_title(tags: dict[str, str]) -> str | None:
    value = tags.get("wikipedia", "")
    lowered = value.lower()
    for prefix in _ZH_PREFIXES:
        if lowered.startswith(prefix):
            return value[len(prefix) :] or None
    return None


def parse_elements(elements: list[dict]) -> list[Candidate]:
    candidates = []
    for element in elements:
        tags = element.get("tags", {})
        if not tags.get("name", "").strip():
            continue
        if "lat" in element and "lon" in element:
            lat, lon = element["lat"], element["lon"]
        elif "center" in element:
            lat, lon = element["center"]["lat"], element["center"]["lon"]
        else:
            continue
        candidates.append(
            Candidate(
                id=f"osm:{element['type']}:{element['id']}",
                name=tags["name"],
                lat=lat,
                lon=lon,
                tags=tags,
                wiki_title=_wiki_title(tags),
            )
        )
    return candidates


class OverpassClient:
    def __init__(self, http: RetryingHttp, cache: JsonCache, urls: tuple[str, ...] = OVERPASS_URLS):
        self._http = http
        self._cache = cache
        self._urls = urls

    async def nearby(self, box: BBox) -> list[Candidate]:
        query = build_query(box)
        elements = self._cache.get(query)
        if elements is None:
            elements = await self._fetch(query)
            self._cache.set(query, elements)
        return parse_elements(elements)

    async def _fetch(self, query: str) -> list[dict]:
        last = len(self._urls) - 1
        for i, url in enumerate(self._urls):
            try:
                # 最後一站才做完整退避；前面的站失敗就直接換站
                response = await self._http.request(
                    "POST", url, data={"data": query}, backoff=None if i == last else ()
                )
                response.raise_for_status()
                return response.json().get("elements", [])
            except httpx2.HTTPError:
                if i == last:
                    raise
        raise AssertionError("unreachable")
