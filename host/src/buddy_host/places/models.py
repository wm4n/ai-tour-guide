from dataclasses import dataclass, field


@dataclass(frozen=True)
class Location:
    lat: float
    lon: float
    heading_deg: float | None = None  # 行進方向，0＝北；未知時為 None


@dataclass(frozen=True)
class BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@dataclass(frozen=True)
class Candidate:
    id: str
    name: str
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)
    wiki_title: str | None = None
    wiki_extract: str | None = None
