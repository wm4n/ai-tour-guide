"""POI Service: combines Overpass, Wikipedia, filter, confidence, and cache."""

import datetime
import logging
import math

from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event
from tour_guide.models.poi import POI, BBox, Place, POIContext, TagFilter, WikiArticle
from tour_guide.services.confidence import ConfidenceClassifier
from tour_guide.services.foodie_filter import filter_places
from tour_guide.services.poi_filter import filter_poi_nodes
from tour_guide.services.wikipedia_resolver import WikipediaResolver

logger = logging.getLogger(__name__)

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


def _place_to_poi(place: Place, user_lat: float, user_lon: float) -> POI:
    """Convert a Google Places Place to a POI dataclass."""
    confidence = ConfidenceClassifier.classify_place(place)
    distance = _haversine(user_lat, user_lon, place.lat, place.lon)
    return POI(
        id=place.id,
        name=place.name,
        lat=place.lat,
        lon=place.lon,
        tags={},
        wiki=None,
        distance_m=distance,
        confidence=confidence,
        rating=place.rating,
        user_ratings_total=place.user_ratings_total,
        price_level=place.price_level,
        place_types=place.types,
        vicinity=place.vicinity,
    )


class POIService:
    def __init__(
        self,
        overpass: OverpassClient,
        wikipedia: WikipediaClient,
        cache: POICache,
        google_places=None,
        resolver: WikipediaResolver | None = None,
    ):
        self._overpass = overpass
        self._wikipedia = wikipedia
        self._cache = cache
        self._google_places = google_places
        self._resolver = resolver

    async def nearby(
        self,
        lat: float,
        lon: float,
        radius: int,
        persona: str,
        lang: str,
    ) -> list[POI]:
        if persona == "foodie":
            return await self._nearby_foodie(lat, lon, radius)
        return await self._nearby_osm(lat, lon, radius, lang)

    async def _nearby_foodie(self, lat: float, lon: float, radius: int) -> list[POI]:
        if self._google_places is None:
            return []

        region_key = f"region:foodie:{lat:.3f}:{lon:.3f}:{radius}"
        cached = self._cache.get(region_key)
        if cached is not None:
            return [
                POI(
                    id=p["id"], name=p["name"], lat=p["lat"], lon=p["lon"],
                    tags=p["tags"], wiki=None,
                    distance_m=p["distance_m"], confidence=p["confidence"],
                    rating=p.get("rating"), user_ratings_total=p.get("user_ratings_total"),
                    price_level=p.get("price_level"), place_types=p.get("place_types"),
                    vicinity=p.get("vicinity"),
                )
                for p in cached
            ]

        current_hour = datetime.datetime.now().hour
        places = await self._google_places.nearby_restaurants(lat, lon, radius)
        filtered = filter_places(places, current_hour)
        pois = [_place_to_poi(p, lat, lon) for p in filtered]
        pois.sort(key=lambda p: p.distance_m)

        self._cache.put(
            region_key,
            [
                {
                    "id": p.id, "name": p.name, "lat": p.lat, "lon": p.lon,
                    "tags": p.tags, "distance_m": p.distance_m, "confidence": p.confidence,
                    "rating": p.rating, "user_ratings_total": p.user_ratings_total,
                    "price_level": p.price_level, "place_types": p.place_types,
                    "vicinity": p.vicinity,
                }
                for p in pois
            ],
        )
        return pois

    async def _nearby_osm(self, lat: float, lon: float, radius: int, lang: str) -> list[POI]:
        region_key = f"region:{lat:.3f}:{lon:.3f}:{radius}:{lang}"
        cached = self._cache.get(region_key)
        if cached is not None:
            log_event(logger, LogEvents.POI_CACHE_HIT, level="debug", key=region_key)
            return [
                POI(
                    id=p["id"], name=p["name"], lat=p["lat"], lon=p["lon"],
                    tags=p["tags"],
                    wiki=WikiArticle(**p["wiki"]) if p["wiki"] else None,
                    distance_m=p["distance_m"], confidence=p["confidence"],
                )
                for p in cached
            ]

        bbox = _lat_lon_to_bbox(lat, lon, radius)
        try:
            raw_nodes = await self._overpass.query(bbox, _DEFAULT_TAG_FILTERS)
        except Exception as e:
            log_event(
                logger, LogEvents.UPSTREAM_FAIL,
                level="warning", service="overpass", error=type(e).__name__,
            )
            raw_nodes = await self._wikipedia.geosearch(lat, lon, radius, lang)
        filtered = filter_poi_nodes(raw_nodes)

        # Sort by distance and limit to 20 to avoid Wikipedia API floods
        filtered.sort(key=lambda n: _haversine(lat, lon, n.lat, n.lon))
        nearest = filtered[:20]

        pois: list[POI] = []
        for node in nearest:
            wiki_key = node.tags.get("wikipedia", "")
            wiki_title = wiki_key.split(":", 1)[-1] if ":" in wiki_key else wiki_key
            wiki_lang = wiki_key.split(":")[0] if ":" in wiki_key else lang

            wiki = None
            if wiki_title:
                try:
                    wiki = await self._wikipedia.summary(wiki_title, wiki_lang)
                except Exception:
                    log_event(
                        logger, LogEvents.UPSTREAM_FAIL,
                        level="warning", service="wiki", title=wiki_title, lang=wiki_lang,
                    )

            if wiki is None and self._resolver is not None:
                poi_name = node.tags.get("name", "")
                if poi_name:
                    try:
                        wiki = await self._resolver.resolve(poi_name, node.lat, node.lon, lang)
                    except Exception:
                        log_event(
                            logger, LogEvents.UPSTREAM_FAIL,
                            level="warning", service="wiki_resolver", poi_name=poi_name,
                        )

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

        if pois:
            log_event(logger, LogEvents.POI_LOADED, count=len(pois), source="osm")
        else:
            log_event(logger, LogEvents.POI_EMPTY, level="warning", lat=lat, lon=lon, radius=radius)

        self._cache.put(
            region_key,
            [
                {
                    "id": p.id, "name": p.name, "lat": p.lat, "lon": p.lon,
                    "tags": p.tags,
                    "wiki": vars(p.wiki) if p.wiki else None,
                    "distance_m": p.distance_m, "confidence": p.confidence,
                }
                for p in pois
            ],
        )
        return pois
