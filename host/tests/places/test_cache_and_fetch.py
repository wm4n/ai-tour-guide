import httpx2
import pytest

from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import USER_AGENT, RetryingHttp


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_cache_roundtrip_and_expiry(tmp_path):
    clock = Clock()
    cache = JsonCache(tmp_path, ttl_seconds=60, clock=clock)

    assert cache.get("k") is None
    cache.set("k", {"a": [1, 2]})
    assert cache.get("k") == {"a": [1, 2]}

    clock.now += 61
    assert cache.get("k") is None


def test_cache_survives_a_new_instance(tmp_path):
    JsonCache(tmp_path, ttl_seconds=60).set("k", ["x"])

    assert JsonCache(tmp_path, ttl_seconds=60).get("k") == ["x"]


def test_cache_tolerates_corrupt_files(tmp_path):
    cache = JsonCache(tmp_path, ttl_seconds=60)
    cache.set("k", 1)
    for f in tmp_path.iterdir():
        f.write_text("{not json")

    assert cache.get("k") is None


def make_http(handler, sleeps, backoff=(1, 2, 4)):
    async def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return RetryingHttp(client, backoff=backoff, sleep=fake_sleep)


async def test_sends_an_identifiable_user_agent():
    seen = []

    def handler(request):
        seen.append(request.headers["user-agent"])
        return httpx2.Response(200, json={})

    await make_http(handler, []).request("GET", "https://example.test/x")

    assert seen == [USER_AGENT]
    assert "github.com/wm4n/ai-tour-guide" in USER_AGENT


async def test_retries_5xx_and_429_with_backoff_then_succeeds():
    statuses = iter([503, 429, 200])
    sleeps: list[float] = []

    def handler(request):
        return httpx2.Response(next(statuses), json={"ok": True})

    response = await make_http(handler, sleeps).request("GET", "https://example.test/x")

    assert response.json() == {"ok": True}
    assert sleeps == [1, 2]


async def test_gives_up_after_the_backoff_is_exhausted():
    sleeps: list[float] = []
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(503)

    with pytest.raises(httpx2.HTTPStatusError):
        await make_http(handler, sleeps).request("GET", "https://example.test/x")

    assert len(calls) == 4
    assert sleeps == [1, 2, 4]


async def test_retries_network_errors():
    attempts = []

    def handler(request):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx2.ConnectError("boom")
        return httpx2.Response(200, json={})

    await make_http(handler, []).request("GET", "https://example.test/x")

    assert len(attempts) == 2


async def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(404)

    response = await make_http(handler, []).request("GET", "https://example.test/x")

    assert response.status_code == 404
    assert len(calls) == 1


async def test_retry_after_header_is_honoured_when_longer_than_the_backoff():
    responses = iter(
        [
            httpx2.Response(429, headers={"Retry-After": "7"}),
            httpx2.Response(200, json={}),
        ]
    )
    sleeps: list[float] = []

    def handler(request):
        return next(responses)

    await make_http(handler, sleeps).request("GET", "https://example.test/x")

    assert sleeps == [7]


async def test_absurd_retry_after_is_capped():
    responses = iter([httpx2.Response(503, headers={"Retry-After": "3600"}), httpx2.Response(200)])
    sleeps: list[float] = []

    await make_http(lambda r: next(responses), sleeps).request("GET", "https://example.test/x")

    assert sleeps == [30]


async def test_backoff_can_be_overridden_per_request():
    sleeps: list[float] = []
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(503)

    with pytest.raises(httpx2.HTTPStatusError):
        await make_http(handler, sleeps).request("GET", "https://example.test/x", backoff=())

    assert len(calls) == 1
    assert sleeps == []
