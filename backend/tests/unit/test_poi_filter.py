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
        """Node with tourism=museum but NO wikipedia/wikidata should be excluded."""
        node = OsmNode(
            id="osm:node:2",
            lat=25.0455,
            lon=121.5681,
            tags={
                "name": "Local Museum",
                "tourism": "museum",
            },
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
        """Node with historic=monument AND wikidata=Q12345 should pass."""
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
            tags={"tourism": "museum", "wikipedia": "en:Museum"},
        )
        invalid_no_wiki = OsmNode(
            id="osm:node:11",
            lat=25.0,
            lon=121.5,
            tags={"tourism": "cafe"},
        )
        invalid_no_category = OsmNode(
            id="osm:node:12",
            lat=25.0,
            lon=121.5,
            tags={"shop": "book", "wikipedia": "en:Bookstore"},
        )
        valid_historic = OsmNode(
            id="osm:node:13",
            lat=25.0,
            lon=121.5,
            tags={"historic": "castle", "wikidata": "Q999"},
        )

        result = filter_poi_nodes(
            [
                valid_museum,
                invalid_no_wiki,
                invalid_no_category,
                valid_historic,
            ]
        )

        assert len(result) == 2
        assert valid_museum in result
        assert valid_historic in result
        assert invalid_no_wiki not in result
        assert invalid_no_category not in result

    def test_empty_list_returns_empty(self):
        """Empty input list should return empty list."""
        result = filter_poi_nodes([])
        assert result == []

    def test_node_with_multiple_allowed_keys(self):
        """Node with both tourism AND historic tags should still pass with wiki."""
        node = OsmNode(
            id="osm:node:14",
            lat=25.0,
            lon=121.5,
            tags={
                "tourism": "attraction",
                "historic": "building",
                "wikipedia": "en:Building",
            },
        )
        result = filter_poi_nodes([node])
        assert len(result) == 1
        assert result[0] == node
