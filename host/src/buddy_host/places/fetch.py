import asyncio
from collections.abc import Awaitable, Callable, Sequence

import httpx2

# Overpass 與 Wikimedia 都要求可識別的 User-Agent
USER_AGENT = "AIBuddyTour/0.1 (https://github.com/wm4n/ai-tour-guide; personal project)"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class RetryingHttp:
    """帶可識別 User-Agent 與指數退避的 HTTP 呼叫。4xx（429 除外）不重試。"""

    def __init__(
        self,
        client: httpx2.AsyncClient,
        backoff: Sequence[float] = (1, 2, 4),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ):
        self._client = client
        self._backoff = tuple(backoff)
        self._sleep = sleep

    async def request(self, method: str, url: str, **kwargs) -> httpx2.Response:
        headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
        waits = [*self._backoff, None]
        for wait in waits:
            try:
                response = await self._client.request(method, url, headers=headers, **kwargs)
                if response.status_code not in RETRY_STATUSES:
                    return response
                if wait is None:
                    response.raise_for_status()
            except httpx2.TransportError:
                if wait is None:
                    raise
            await self._sleep(wait)  # type: ignore[arg-type]
        raise AssertionError("unreachable")
