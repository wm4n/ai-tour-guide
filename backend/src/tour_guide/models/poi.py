from dataclasses import dataclass, field


@dataclass
class OsmNode:
    id: str          # e.g. "osm:node:12345"
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class WikiArticle:
    title: str
    extract: str     # intro text
    url: str
    lang: str


@dataclass
class POIContext:
    osm: OsmNode
    wiki: WikiArticle | None = None


@dataclass
class POI:
    id: str
    name: str
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)
    wiki: WikiArticle | None = None
    distance_m: float = 0.0
    confidence: str = "low"   # "high" | "medium" | "low"


@dataclass
class BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@dataclass
class TagFilter:
    key: str
    values: list[str] = field(default_factory=list)  # empty = any value
