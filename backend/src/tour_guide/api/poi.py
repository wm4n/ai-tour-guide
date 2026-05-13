"""POI API endpoint for querying nearby points of interest."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from tour_guide.clients.overpass import OverpassRateLimitError
from tour_guide.services.poi_service import POIService

router = APIRouter()


def get_poi_service() -> POIService:
    raise NotImplementedError("Override with dependency")


@router.get("/poi/nearby")
async def poi_nearby(
    lat: float = Query(..., ge=-90, le=90, description="Latitude (-90 to 90)"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude (-180 to 180)"),
    radius: int = Query(500, ge=1, le=5000, description="Search radius in meters"),
    lang: str = Query("zh-TW", description="Language code"),
    persona: str = Query("history_uncle", description="User persona"),
    poi_service: POIService = Depends(get_poi_service),  # noqa: B008
):
    try:
        pois = await poi_service.nearby(lat, lon, radius, persona, lang)
        return {
            "pois": [_serialize_poi(p) for p in pois],
            "queried_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }
    except OverpassRateLimitError as e:
        return JSONResponse(
            status_code=429,
            content={"detail": "Overpass rate limit exceeded"},
            headers={"Retry-After": str(e.retry_after_s)},
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Upstream service unavailable") from e


def _serialize_poi(p) -> dict:
    result = {
        "id": p.id,
        "name": p.name,
        "lat": p.lat,
        "lon": p.lon,
        "tags": p.tags,
        "wiki": {
            "title": p.wiki.title,
            "extract": p.wiki.extract,
            "url": p.wiki.url,
            "lang": p.wiki.lang,
        } if p.wiki else None,
        "distance_m": p.distance_m,
        "confidence": p.confidence,
    }
    if p.rating is not None:
        result["rating"] = p.rating
        result["user_ratings_total"] = p.user_ratings_total
        result["price_level"] = p.price_level
        result["place_types"] = p.place_types
        result["vicinity"] = p.vicinity
    return result
