"""Tests for POI filter service."""

from tour_guide.models.poi import OsmNode
from tour_guide.services.poi_filter import filter_poi_nodes


class TestFilterPOINodes:
    """Test the POI filter logic."""

    def test_node_with_tourism_and_wikipedia_passes(self):
        """Node with tourism=museum AND wikipedia=zh:故宮 should pass."""
        node = OsmNode(
            id="osm:node:1",
            lat=25.0455,
            lon=121.5681,
            tags={
                "name": "National Palace Museum",
                "tourism": "museum",
                "wikipedia": "zh:故宮博物院",
            },
        )
        result = filter_poi_nodes([node])
        assert len(result) == 1
        assert result[0] == node

    def test_node_with_tourism_but_no_wiki_excluded(self):
        """Node with tourism=museum but NO name tag should be excluded (no wiki needed)."""
        node = OsmNode(
            id="osm:node:2",
            lat=25.0455,
            lon=121.5681,
            tags={"tourism": "museum"},  # no name tag
        )
        result = filter_poi_nodes([node])
        assert len(result) == 0

    def test_node_with_shop_only_excluded(self):
        """Node with shop=convenience (no tourism/historic) should be excluded."""
        node = OsmNode(
            id="osm:node:3",
            lat=25.0455,
            lon=121.5681,
            tags={
                "name": "7-Eleven",
                "shop": "convenience",
                "wikipedia": "en:7-Eleven",  # Even with wiki tag
            },
        )
        result = filter_poi_nodes([node])
        assert len(result) == 0

    def test_node_with_historic_and_wikidata_passes(self):
        """Node with historic=monument AND name should pass (wikidata optional)."""
        node = OsmNode(
            id="osm:node:4",
            lat=25.0455,
            lon=121.5681,
            tags={
                "name": "Historical Monument",
                "historic": "monument",
                "wikidata": "Q12345",
            },
        )
        result = filter_poi_nodes([node])
        assert len(result) == 1
        assert result[0] == node

    def test_mixed_nodes_filtering(self):
        """Test filtering with a mix of valid and invalid nodes."""
        valid_museum = OsmNode(
            id="osm:node:10",
            lat=25.0,
            lon=121.5,
            tags={"name": "Some Museum", "tourism": "museum"},
        )
        invalid_no_name = OsmNode(
            id="osm:node:11",
            lat=25.0,
            lon=121.5,
            tags={"tourism": "cafe"},  # no name tag
        )
        invalid_no_category = OsmNode(
            id="osm:node:12",
            lat=25.0,
            lon=121.5,
            tags={"name": "Bookstore", "shop": "book"},  # no tourism/historic
        )
        valid_historic = OsmNode(
            id="osm:node:13",
            lat=25.0,
            lon=121.5,
            tags={"name": "Old Castle", "historic": "castle"},
        )

        result = filter_poi_nodes([valid_museum, invalid_no_name, invalid_no_category, valid_historic])

        assert len(result) == 2
        assert valid_museum in result
        assert valid_historic in result
        assert invalid_no_name not in result
        assert invalid_no_category not in result

    def test_empty_list_returns_empty(self):
        """Empty input list should return empty list."""
        result = filter_poi_nodes([])
        assert result == []

    def test_node_with_multiple_allowed_keys(self):
        """Node with both tourism AND historic tags should pass with name."""
        node = OsmNode(
            id="osm:node:14",
            lat=25.0,
            lon=121.5,
            tags={
                "name": "Historic Attraction",
                "tourism": "attraction",
                "historic": "building",
                "wikipedia": "en:Building",
            },
        )
        result = filter_poi_nodes([node])
        assert len(result) == 1
        assert result[0] == node

    def test_node_with_tourism_and_name_but_no_wiki_now_passes(self):
        """After relaxation: tourism+name node WITHOUT wiki tag should pass."""
        node = OsmNode(
            id="osm:node:99",
            lat=25.0,
            lon=121.5,
            tags={"name": "Local Museum", "tourism": "museum"},
        )
        result = filter_poi_nodes([node])
        assert len(result) == 1

    def test_node_with_tourism_but_no_name_excluded(self):
        """Node with tourism but no name tag should be excluded."""
        node = OsmNode(
            id="osm:node:100",
            lat=25.0,
            lon=121.5,
            tags={"tourism": "museum"},
        )
        result = filter_poi_nodes([node])
        assert len(result) == 0
