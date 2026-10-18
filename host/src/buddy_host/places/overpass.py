"""Overpass（OpenStreetMap）：找出附近的景點、古蹟、廟宇，以及有故事的老店。"""

from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp
from buddy_host.places.models import BBox, Candidate

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

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
    def __init__(self, http: RetryingHttp, cache: JsonCache, url: str = OVERPASS_URL):
        self._http = http
        self._cache = cache
        self._url = url

    async def nearby(self, box: BBox) -> list[Candidate]:
        query = build_query(box)
        elements = self._cache.get(query)
        if elements is None:
            response = await self._http.request("POST", self._url, data={"data": query})
            response.raise_for_status()
            elements = response.json().get("elements", [])
            self._cache.set(query, elements)
        return parse_elements(elements)
