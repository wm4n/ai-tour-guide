"""POI Service: combines Overpass, Wikipedia, filter, confidence, and cache."""

import math

from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import POI, BBox, POIContext, TagFilter, WikiArticle
from tour_guide.services.confidence import ConfidenceClassifier
from tour_guide.services.poi_filter import filter_poi_nodes

_DEFAULT_TAG_FILTERS = [
    TagFilter(key="tourism"),
    TagFilter(key="historic"),
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lat_lon_to_bbox(lat: float, lon: float, radius_m: int) -> BBox:
    delta_lat = radius_m / 111_320
    delta_lon = radius_m / (111_320 * math.cos(math.radians(lat)))
    return BBox(lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


class POIService:
    def __init__(
        self,
        overpass: OverpassClient,
        wikipedia: WikipediaClient,
        cache: POICache,
    ):
        self._overpass = overpass
        self._wikipedia = wikipedia
        self._cache = cache

    async def nearby(
        self,
        lat: float,
        lon: float,
        radius: int,
        persona: str,
        lang: str,
    ) -> list[POI]:
        # Region cache key (persona excluded: same POIs regardless of persona)
        region_key = f"region:{lat:.3f}:{lon:.3f}:{radius}:{lang}"
        cached = self._cache.get(region_key)
        if cached is not None:
            return [
                POI(
                    id=p["id"],
                    name=p["name"],
                    lat=p["lat"],
                    lon=p["lon"],
                    tags=p["tags"],
                    wiki=WikiArticle(**p["wiki"]) if p["wiki"] else None,
                    distance_m=p["distance_m"],
                    confidence=p["confidence"],
                )
                for p in cached
            ]

        bbox = _lat_lon_to_bbox(lat, lon, radius)
        raw_nodes = await self._overpass.query(bbox, _DEFAULT_TAG_FILTERS)
        filtered = filter_poi_nodes(raw_nodes)

        pois: list[POI] = []
        for node in filtered:
            wiki_key = node.tags.get("wikipedia", "")
            wiki_title = wiki_key.split(":", 1)[-1] if ":" in wiki_key else wiki_key
            wiki_lang = wiki_key.split(":")[0] if ":" in wiki_key else lang

            wiki = None
            if wiki_title:
                wiki = await self._wikipedia.summary(wiki_title, wiki_lang)

            poi_context = POIContext(osm=node, wiki=wiki)
            confidence = ConfidenceClassifier.classify(poi_context)
            distance = _haversine(lat, lon, node.lat, node.lon)

            pois.append(
                POI(
                    id=node.id,
                    name=node.tags.get("name", node.id),
                    lat=node.lat,
                    lon=node.lon,
                    tags=node.tags,
                    wiki=wiki,
                    distance_m=distance,
                    confidence=confidence,
                )
            )

        pois.sort(key=lambda p: p.distance_m)

        # Cache the serialized results
        self._cache.put(
            region_key,
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "lat": p.lat,
                    "lon": p.lon,
                    "tags": p.tags,
                    "wiki": vars(p.wiki) if p.wiki else None,
                    "distance_m": p.distance_m,
                    "confidence": p.confidence,
                }
                for p in pois
            ],
        )

        return pois
