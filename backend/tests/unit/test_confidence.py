from tour_guide.models.poi import OsmNode, POIContext, Place, WikiArticle
from tour_guide.services.confidence import ConfidenceClassifier


class TestConfidenceClassifier:
    def test_classify_high_confidence_with_200_chars(self):
        """Returns 'high' when wiki extract has >= 200 chars"""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        wiki = WikiArticle(
            title="Taipei 101",
            extract="a" * 200,  # exactly 200 characters
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        poi_context = POIContext(osm=osm, wiki=wiki)
        assert ConfidenceClassifier.classify(poi_context) == "high"

    def test_classify_high_confidence_with_more_than_200_chars(self):
        """Returns 'high' when wiki extract has > 200 chars"""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        wiki = WikiArticle(
            title="Taipei 101",
            extract="a" * 300,  # 300 characters
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        poi_context = POIContext(osm=osm, wiki=wiki)
        assert ConfidenceClassifier.classify(poi_context) == "high"

    def test_classify_medium_confidence_with_less_than_200_chars(self):
        """Returns 'medium' when wiki extract has < 200 chars (but > 0)"""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        wiki = WikiArticle(
            title="Taipei 101",
            extract="This is a short extract about Taipei 101.",  # < 200 chars
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        poi_context = POIContext(osm=osm, wiki=wiki)
        assert ConfidenceClassifier.classify(poi_context) == "medium"

    def test_classify_medium_confidence_with_199_chars(self):
        """Returns 'medium' when wiki extract has exactly 199 chars"""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        wiki = WikiArticle(
            title="Taipei 101",
            extract="a" * 199,  # exactly 199 characters
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        poi_context = POIContext(osm=osm, wiki=wiki)
        assert ConfidenceClassifier.classify(poi_context) == "medium"

    def test_classify_low_confidence_with_no_wiki(self):
        """Returns 'low' when poi_context.wiki is None"""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        poi_context = POIContext(osm=osm, wiki=None)
        assert ConfidenceClassifier.classify(poi_context) == "low"

    def test_classify_low_confidence_with_empty_extract(self):
        """Returns 'low' when wiki extract is empty string"""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        wiki = WikiArticle(
            title="Taipei 101",
            extract="",  # empty extract
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        poi_context = POIContext(osm=osm, wiki=wiki)
        assert ConfidenceClassifier.classify(poi_context) == "low"


class TestConfidenceClassifierPlace:
    """Tests for ConfidenceClassifier.classify_place()."""

    def test_high_when_above_both_thresholds(self):
        place = Place(
            id="gplace:001", name="名店", lat=25.0, lon=121.0,
            rating=4.5, user_ratings_total=100, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "high"

    def test_high_boundary_exactly_45_and_100(self):
        place = Place(
            id="gplace:002", name="名店", lat=25.0, lon=121.0,
            rating=4.5, user_ratings_total=100, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "high"

    def test_medium_when_rating_below_45(self):
        place = Place(
            id="gplace:003", name="中等", lat=25.0, lon=121.0,
            rating=4.3, user_ratings_total=200, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "medium"

    def test_medium_when_count_below_100(self):
        place = Place(
            id="gplace:004", name="中等", lat=25.0, lon=121.0,
            rating=4.8, user_ratings_total=50, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "medium"

    def test_low_when_rating_none(self):
        place = Place(
            id="gplace:005", name="無評", lat=25.0, lon=121.0,
            rating=None, user_ratings_total=None, price_level=None,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "low"
