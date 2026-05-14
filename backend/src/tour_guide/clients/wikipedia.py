"""Wikipedia REST API client."""

import logging
import time

import httpx

from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event
from tour_guide.models.poi import WikiArticle

logger = logging.getLogger(__name__)

# BCP 47 tags that Wikipedia doesn't use as subdomains
_LANG_MAP = {
    "zh-TW": "zh",
    "zh-HK": "zh",
    "zh-SG": "zh",
    "zh-CN": "zh",
}


class WikipediaClient:
    BASE_URL = "https://{lang}.wikipedia.org/api/rest_v1"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient()

    async def summary(self, title: str, lang: str) -> WikiArticle | None:
        wiki_lang = _LANG_MAP.get(lang, lang)
        url = f"https://{wiki_lang}.wikipedia.org/api/rest_v1/page/summary/{title}"
        start = time.monotonic()
        log_event(logger, LogEvents.WIKI_REQUEST, level="debug", title=title, lang=wiki_lang)
        resp = await self._client.get(url)
        elapsed_ms = int((time.monotonic() - start) * 1000)
        if resp.status_code == 404:
            log_event(logger, LogEvents.WIKI_RESPONSE, level="debug", found=False, duration_ms=elapsed_ms)
            return None
        resp.raise_for_status()
        data = resp.json()
        if data.get("type") == "disambiguation":
            log_event(logger, LogEvents.WIKI_RESPONSE, level="debug", found=False, duration_ms=elapsed_ms)
            return None
        log_event(logger, LogEvents.WIKI_RESPONSE, level="debug", found=True, duration_ms=elapsed_ms)
        return WikiArticle(
            title=data["title"],
            extract=data.get("extract", ""),
            url=data.get("content_urls", {}).get("desktop", {}).get("page", ""),
            lang=lang,
        )
