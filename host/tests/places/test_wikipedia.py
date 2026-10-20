import httpx2

from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp
from buddy_host.places.wikipedia import WikipediaClient


def make_client(handler, tmp_path):
    async def fake_sleep(seconds: float) -> None:
        pass

    http = RetryingHttp(
        httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), sleep=fake_sleep
    )
    return WikipediaClient(http, JsonCache(tmp_path, ttl_seconds=3600))


async def test_summary_returns_title_extract_and_url(tmp_path):
    def handler(request):
        assert request.url.host == "zh.wikipedia.org"
        assert "/page/summary/" in request.url.path
        return httpx2.Response(
            200,
            json={
                "title": "迪化街",
                "extract": "迪化街是台北市的一條老街。",
                "content_urls": {"desktop": {"page": "https://zh.wikipedia.org/wiki/迪化街"}},
            },
        )

    summary = await make_client(handler, tmp_path).summary("迪化街")

    assert summary.title == "迪化街"
    assert summary.extract.startswith("迪化街是")
    assert summary.url.endswith("迪化街")


async def test_summary_404_and_disambiguation_are_none(tmp_path):
    client = make_client(lambda r: httpx2.Response(404), tmp_path)
    assert await client.summary("不存在") is None

    client = make_client(
        lambda r: httpx2.Response(200, json={"type": "disambiguation", "title": "x"}),
        tmp_path / "b",
    )
    assert await client.summary("歧義") is None


async def test_search_returns_the_first_title(tmp_path):
    def handler(request):
        assert request.url.params["action"] == "opensearch"
        return httpx2.Response(200, json=["霞海", ["台北霞海城隍廟", "別的"], [], []])

    assert await make_client(handler, tmp_path).search("霞海城隍廟") == "台北霞海城隍廟"


async def test_search_without_results_is_none(tmp_path):
    client = make_client(lambda r: httpx2.Response(200, json=["x", [], [], []]), tmp_path)

    assert await client.search("沒有") is None


async def test_geosearch_returns_titles_with_coordinates(tmp_path):
    def handler(request):
        assert request.url.params["list"] == "geosearch"
        assert request.url.params["gscoord"] == "25.05|121.51"
        return httpx2.Response(
            200,
            json={
                "query": {
                    "geosearch": [
                        {"pageid": 1, "title": "迪化街", "lat": 25.06, "lon": 121.51},
                    ]
                }
            },
        )

    hits = await make_client(handler, tmp_path).geosearch(25.05, 121.51, 500)

    assert [(h.title, h.lat, h.lon) for h in hits] == [("迪化街", 25.06, 121.51)]


async def test_results_are_cached(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(200, json={"title": "迪化街", "extract": "x"})

    client = make_client(handler, tmp_path)
    await client.summary("迪化街")
    await client.summary("迪化街")

    assert len(calls) == 1
