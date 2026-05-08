"""Integration tests for POIService: full pipeline with fake clients."""

import pytest

from tour_guide.cache.poi_cache import POICache
from tour_guide.models.poi import OsmNode, WikiArticle
from tour_guide.services.poi_service import POIService

# ---------------------------------------------------------------------------
# Fake clients
# ---------------------------------------------------------------------------

class FakeOverpassClient:
    def __init__(self, nodes):
        self.call_count = 0
        self._nodes = nodes

    async def query(self, bbox, tags):
        self.call_count += 1
        return self._nodes


class FakeWikiClient:
    def __init__(self, article):
        self._article = article

    async def summary(self, title, lang):
        return self._article


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def sample_node():
    return OsmNode(
        id="osm:node:12345",
        lat=25.1023,
        lon=121.5482,
        tags={
            "name": "故宮博物院",
            "tourism": "museum",
            "wikipedia": "zh:國立故宮博物院",
        },
    )


@pytest.fixture()
def sample_article():
    return WikiArticle(
        title="國立故宮博物院",
        # 224 chars (7 * 32), ensuring >= 200 → "high" confidence
        extract="National Palace Museum Taipei Taiwan " * 7,
        url="https://zh.wikipedia.org/wiki/國立故宮博物院",
        lang="zh",
    )


# ---------------------------------------------------------------------------
# Test 1: Full pipeline returns enriched POIs with wiki and confidence
# ---------------------------------------------------------------------------

class TestPOIServiceNearby:
    async def test_full_pipeline_returns_enriched_pois(
        self, tmp_path, sample_node, sample_article
    ):
        """Full pipeline returns POIs with wiki populated and confidence set."""
        overpass = FakeOverpassClient([sample_node])
        wiki = FakeWikiClient(sample_article)
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(overpass=overpass, wikipedia=wiki, cache=cache)
        pois = await service.nearby(25.1023, 121.5482, 500, "history_uncle", "zh-TW")

        assert len(pois) >= 1
        poi = pois[0]
        assert poi.wiki is not None
        assert poi.wiki.title == sample_article.title
        assert poi.confidence in {"high", "medium", "low"}
        assert poi.confidence == "high"  # long extract → high
        assert poi.distance_m >= 0.0

    # ---------------------------------------------------------------------------
    # Test 2: Cache hit skips external client calls
    # ---------------------------------------------------------------------------

    async def test_cache_hit_skips_overpass_query(
        self, tmp_path, sample_node, sample_article
    ):
        """Second nearby() call with same args uses cache; OverpassClient called only once."""
        overpass = FakeOverpassClient([sample_node])
        wiki = FakeWikiClient(sample_article)
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(overpass=overpass, wikipedia=wiki, cache=cache)

        # First call — populates cache
        pois_first = await service.nearby(25.1023, 121.5482, 500, "history_uncle", "zh-TW")

        # Second call — should use cache
        pois_second = await service.nearby(25.1023, 121.5482, 500, "history_uncle", "zh-TW")

        assert overpass.call_count == 1  # Overpass only called once
        assert len(pois_first) == len(pois_second)
        assert pois_first[0].id == pois_second[0].id
        assert pois_second[0].wiki is not None  # wiki correctly deserialized from cache
