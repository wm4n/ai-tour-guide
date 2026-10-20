import httpx2

from buddy_host.places.cache import JsonCache
from buddy_host.places.fetch import RetryingHttp
from buddy_host.places.geo import bounding_box
from buddy_host.places.overpass import OverpassClient

BOX = bounding_box(25.0553, 121.5098, 500)

PAYLOAD = {
    "elements": [
        {
            "type": "node",
            "id": 1,
            "lat": 25.0554,
            "lon": 121.5099,
            "tags": {
                "name": "霞海城隍廟",
                "amenity": "place_of_worship",
                "wikipedia": "zh:霞海城隍廟",
            },
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 25.056, "lon": 121.51},
            "tags": {
                "name": "李春生紀念教會",
                "historic": "building",
                "wikipedia": "en:Some Church",
            },
        },
        {"type": "node", "id": 3, "lat": 25.0551, "lon": 121.5101, "tags": {"tourism": "artwork"}},
        {"type": "relation", "id": 4, "tags": {"name": "沒有座標", "tourism": "museum"}},
    ]
}


def make_client(handler, tmp_path, sleeps=None):
    async def fake_sleep(seconds: float) -> None:
        if sleeps is not None:
            sleeps.append(seconds)

    http = RetryingHttp(
        httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), sleep=fake_sleep
    )
    return OverpassClient(http, JsonCache(tmp_path, ttl_seconds=3600))


async def test_parses_nodes_and_way_centres_and_drops_nameless_or_coordless(tmp_path):
    client = make_client(lambda r: httpx2.Response(200, json=PAYLOAD), tmp_path)

    candidates = await client.nearby(BOX)

    assert [c.id for c in candidates] == ["osm:node:1", "osm:way:2"]
    assert candidates[1].lat == 25.056
    assert candidates[0].tags["amenity"] == "place_of_worship"


async def test_chinese_wikipedia_tag_becomes_wiki_title_other_languages_do_not(tmp_path):
    client = make_client(lambda r: httpx2.Response(200, json=PAYLOAD), tmp_path)

    first, second = await client.nearby(BOX)

    assert first.wiki_title == "霞海城隍廟"
    assert second.wiki_title is None


async def test_query_covers_the_bbox_and_the_interesting_tags(tmp_path):
    bodies = []

    def handler(request):
        bodies.append(request.content.decode())
        return httpx2.Response(200, json={"elements": []})

    await make_client(handler, tmp_path).nearby(BOX)

    from urllib.parse import unquote_plus

    query = unquote_plus(bodies[0])
    assert f"{BOX.min_lat}" in query and f"{BOX.max_lon}" in query
    for key in ("tourism", "historic", "place_of_worship", "start_date", "heritage"):
        assert key in query


async def test_second_identical_call_is_served_from_cache(tmp_path):
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(200, json=PAYLOAD)

    client = make_client(handler, tmp_path)

    first = await client.nearby(BOX)
    second = await client.nearby(BOX)

    assert len(calls) == 1
    assert [c.id for c in second] == [c.id for c in first]


async def test_retries_with_backoff_on_503(tmp_path):
    statuses = iter([503, 200])
    sleeps: list[float] = []

    def handler(request):
        return httpx2.Response(next(statuses), json=PAYLOAD)

    client = make_client(handler, tmp_path, sleeps)
    client._urls = ("https://only.test/api",)

    candidates = await client.nearby(BOX)

    assert len(candidates) == 2
    assert sleeps == [1]


async def test_falls_over_to_the_next_mirror_when_the_first_is_down(tmp_path):
    seen_hosts = []

    def handler(request):
        seen_hosts.append(request.url.host)
        if request.url.host == "a.test":
            return httpx2.Response(502)
        return httpx2.Response(200, json=PAYLOAD)

    async def fake_sleep(seconds: float) -> None:
        pass

    http = RetryingHttp(
        httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), sleep=fake_sleep
    )
    client = OverpassClient(
        http,
        JsonCache(tmp_path, ttl_seconds=3600),
        urls=("https://a.test/api", "https://b.test/api"),
    )

    candidates = await client.nearby(BOX)

    assert len(candidates) == 2
    assert seen_hosts[-1] == "b.test"
    assert seen_hosts.count("a.test") == 1  # 換站時不在壞掉的站上反覆退避


async def test_all_mirrors_down_raises(tmp_path):
    import pytest

    http = RetryingHttp(
        httpx2.AsyncClient(transport=httpx2.MockTransport(lambda r: httpx2.Response(503))),
        sleep=lambda s: _noop(),
    )
    client = OverpassClient(
        http, JsonCache(tmp_path, ttl_seconds=3600), urls=("https://a.test/x", "https://b.test/x")
    )

    with pytest.raises(httpx2.HTTPStatusError):
        await client.nearby(BOX)


async def _noop() -> None:
    return None
