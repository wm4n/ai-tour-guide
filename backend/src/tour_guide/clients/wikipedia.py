"""Wikipedia REST API client."""

import httpx

from tour_guide.models.poi import WikiArticle


class WikipediaClient:
    BASE_URL = "https://{lang}.wikipedia.org/api/rest_v1"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient()

    async def summary(self, title: str, lang: str) -> WikiArticle | None:
        url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
        resp = await self._client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        if data.get("type") == "disambiguation":
            return None
        return WikiArticle(
            title=data["title"],
            extract=data.get("extract", ""),
            url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            lang=lang,
        )
