"""POI filter service for filtering nodes based on taxonomy and metadata."""

from tour_guide.models.poi import OsmNode

_ALLOWED_KEYS = {"tourism", "historic"}


def filter_poi_nodes(nodes: list[OsmNode]) -> list[OsmNode]:
    """Keep nodes that have an allowed tourism/historic tag AND a non-empty name.

    Args:
        nodes: List of OSM nodes to filter.

    Returns:
        List of nodes that have both:
        - At least one allowed key (tourism or historic)
        - A non-empty 'name' tag
    """
    result = []
    for node in nodes:
        has_allowed = any(k in _ALLOWED_KEYS for k in node.tags)
        has_name = bool(node.tags.get("name", "").strip())
        if has_allowed and has_name:
            result.append(node)
    return result
