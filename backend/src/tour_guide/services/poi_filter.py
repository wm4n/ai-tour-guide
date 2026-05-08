"""POI filter service for filtering nodes based on taxonomy and metadata."""

from tour_guide.models.poi import OsmNode

_ALLOWED_KEYS = {"tourism", "historic"}
_WIKI_KEYS = {"wikipedia", "wikidata"}


def filter_poi_nodes(nodes: list[OsmNode]) -> list[OsmNode]:
    """Keep nodes that have an allowed tourism/historic tag AND a wikipedia/wikidata tag.

    Args:
        nodes: List of OSM nodes to filter.

    Returns:
        List of nodes that have both:
        - At least one allowed key (tourism or historic)
        - At least one wiki key (wikipedia or wikidata)
    """
    result = []
    for node in nodes:
        has_allowed = any(k in _ALLOWED_KEYS for k in node.tags)
        has_wiki = any(k in _WIKI_KEYS for k in node.tags)
        if has_allowed and has_wiki:
            result.append(node)
    return result
