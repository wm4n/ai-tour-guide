"""Integration tests for POIService: full pipeline with fake clients."""

import pytest

from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.google_places import FakeGooglePlacesClient
from tour_guide.models.poi import OsmNode, Place, WikiArticle
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
    async def test_full_pipeline_returns_enriched_pois(self, tmp_path, sample_node, sample_article):
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

    async def test_cache_hit_skips_overpass_query(self, tmp_path, sample_node, sample_article):
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


class TestPOIServiceFoodieRouting:
    """Tests for POIService persona-aware routing."""

    @pytest.fixture()
    def sample_place(self):
        return Place(
            id="gplace:ChIJ001",
            name="鼎泰豐",
            lat=25.033,
            lon=121.564,
            rating=4.6,
            user_ratings_total=328,
            price_level=2,
            types=["restaurant"],
            vicinity="信義區",
        )

    async def test_foodie_persona_uses_google_places(self, tmp_path, sample_place):
        """persona='foodie' → GooglePlacesClient called, not Overpass."""
        fake_gp = FakeGooglePlacesClient(scripted_places=[sample_place])
        fake_overpass = FakeOverpassClient([])  # should NOT be called
        fake_wiki = FakeWikiClient(None)
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(
            overpass=fake_overpass,
            wikipedia=fake_wiki,
            cache=cache,
            google_places=fake_gp,
        )
        pois = await service.nearby(25.033, 121.564, 500, "foodie", "zh-TW")

        assert fake_overpass.call_count == 0
        assert len(pois) == 1
        assert pois[0].id == "gplace:ChIJ001"
        assert pois[0].rating == 4.6
        assert pois[0].user_ratings_total == 328

    async def test_non_foodie_persona_uses_overpass(self, tmp_path, sample_node, sample_article):
        """persona='history_uncle' → OverpassClient called, not GooglePlaces."""
        fake_gp = FakeGooglePlacesClient(scripted_places=[])
        fake_overpass = FakeOverpassClient([sample_node])
        fake_wiki = FakeWikiClient(sample_article)
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(
            overpass=fake_overpass,
            wikipedia=fake_wiki,
            cache=cache,
            google_places=fake_gp,
        )
        pois = await service.nearby(25.1023, 121.5482, 500, "history_uncle", "zh-TW")

        assert fake_overpass.call_count == 1
        assert pois[0].rating is None  # non-foodie POI has no rating

    async def test_foodie_poi_has_no_wiki(self, tmp_path, sample_place):
        """Foodie POIs converted from Place have wiki=None."""
        fake_gp = FakeGooglePlacesClient(scripted_places=[sample_place])
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(
            overpass=FakeOverpassClient([]),
            wikipedia=FakeWikiClient(None),
            cache=cache,
            google_places=fake_gp,
        )
        pois = await service.nearby(25.033, 121.564, 500, "foodie", "zh-TW")

        assert pois[0].wiki is None
        assert pois[0].place_types == ["restaurant"]
        assert pois[0].vicinity == "信義區"
