"""中文維基百科：標題搜尋、座標搜尋、條目摘要。"""

from dataclasses import dataclass
from urllib.parse import quote

from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp

_API = "https://zh.wikipedia.org/w/api.php"
_SUMMARY = "https://zh.wikipedia.org/api/rest_v1/page/summary/{title}"
_HEADERS = {"Accept-Language": "zh-TW"}


@dataclass(frozen=True)
class WikiSummary:
    title: str
    extract: str
    url: str


@dataclass(frozen=True)
class WikiHit:
    title: str
    lat: float
    lon: float


class WikipediaClient:
    def __init__(self, http: RetryingHttp, cache: JsonCache):
        self._http = http
        self._cache = cache

    async def _get_json(self, key: str, url: str, **kwargs):
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        response = await self._http.request("GET", url, headers=_HEADERS, **kwargs)
        if response.status_code == 404:
            value = {"missing": True}
        else:
            response.raise_for_status()
            value = response.json()
        self._cache.set(key, value)
        return value

    async def summary(self, title: str) -> WikiSummary | None:
        data = await self._get_json(
            f"summary:{title}", _SUMMARY.format(title=quote(title.replace(" ", "_"), safe=""))
        )
        if isinstance(data, dict) and (data.get("missing") or data.get("type") == "disambiguation"):
            return None
        return WikiSummary(
            title=data["title"],
            extract=data.get("extract", ""),
            url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
        )

    async def search(self, query: str) -> str | None:
        params = {"action": "opensearch", "search": query, "limit": "1", "format": "json"}
        data = await self._get_json(f"search:{query}", _API, params=params)
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        return titles[0] if titles else None

    async def geosearch(self, lat: float, lon: float, radius_m: int) -> list[WikiHit]:
        params = {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": str(radius_m),
            "gslimit": "50",
            "format": "json",
        }
        data = await self._get_json(f"geo:{lat}|{lon}|{radius_m}", _API, params=params)
        rows = data.get("query", {}).get("geosearch", []) if isinstance(data, dict) else []
        return [WikiHit(r["title"], r["lat"], r["lon"]) for r in rows]
