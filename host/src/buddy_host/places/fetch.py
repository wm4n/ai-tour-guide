import asyncio
from collections.abc import Awaitable, Callable, Sequence

import httpx2

# Overpass 與 Wikimedia 都要求可識別的 User-Agent
USER_AGENT = "AIBuddyTour/0.1 (https://github.com/wm4n/ai-tour-guide; personal project)"
RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER_SECONDS = 30.0


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
        override = kwargs.pop("backoff", None)  # 例如換鏡像站時不想在壞站上反覆退避
        for wait in self._backoff if override is None else tuple(override):
            delay = wait
            try:
                response = await self._client.request(method, url, headers=headers, **kwargs)
                if response.status_code not in RETRY_STATUSES:
                    return response
                delay = max(wait, _retry_after_seconds(response))
            except httpx2.TransportError:
                pass
            await self._sleep(delay)
        # 最後一次：失敗就把錯誤拋給呼叫端
        response = await self._client.request(method, url, headers=headers, **kwargs)
        if response.status_code in RETRY_STATUSES:
            response.raise_for_status()
        return response


def _retry_after_seconds(response: httpx2.Response) -> float:
    try:
        return min(float(response.headers.get("Retry-After", 0)), MAX_RETRY_AFTER_SECONDS)
    except ValueError:  # HTTP-date 形式不處理，沿用退避
        return 0.0
