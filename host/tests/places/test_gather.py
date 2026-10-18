import pytest

from buddy_host.places.gather import gather_candidates
from buddy_host.places.models import Candidate
from buddy_host.places.wikipedia import WikiHit

OSM = Candidate("osm:node:1", "霞海城隍廟", 25.0554, 121.5099, {"amenity": "place_of_worship"})
HIT = WikiHit("迪化街", 25.06, 121.51)


class Overpass:
    def __init__(self, result):
        self.result = result

    async def nearby(self, box):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class Wiki:
    def __init__(self, result):
        self.result = result

    async def geosearch(self, lat, lon, radius_m):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


async def test_both_sources_are_merged():
    merged = await gather_candidates(Overpass([OSM]), Wiki([HIT]), 25.0553, 121.5098, 500)

    assert {c.name for c in merged} == {"霞海城隍廟", "迪化街"}


async def test_overpass_outage_degrades_to_wikipedia_only():
    merged = await gather_candidates(
        Overpass(RuntimeError("502")), Wiki([HIT]), 25.0553, 121.5098, 500
    )

    assert [c.name for c in merged] == ["迪化街"]


async def test_wikipedia_outage_degrades_to_osm_only():
    merged = await gather_candidates(
        Overpass([OSM]), Wiki(RuntimeError("down")), 25.0553, 121.5098, 500
    )

    assert [c.name for c in merged] == ["霞海城隍廟"]


async def test_both_failing_raises_the_overpass_error():
    with pytest.raises(RuntimeError, match="overpass down"):
        await gather_candidates(
            Overpass(RuntimeError("overpass down")),
            Wiki(RuntimeError("wiki down")),
            25.0553,
            121.5098,
            500,
        )


async def test_both_empty_is_just_empty():
    assert await gather_candidates(Overpass([]), Wiki([]), 25.0553, 121.5098, 500) == []
