"""POST /narration — SSE streaming endpoint for tour guide narration."""

import dataclasses
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from tour_guide.api.sse import encode_event
from tour_guide.models.persona import PersonaConfig
from tour_guide.models.poi import OsmNode, POIContext, WikiArticle
from tour_guide.services.narration_service import NarrationService

router = APIRouter()
logger = logging.getLogger(__name__)


class POICandidate(BaseModel):
    poi_id: str
    poi_name: str = ""
    poi_lat: float = 0.0
    poi_lon: float = 0.0
    distance_m: float = 0.0
    poi_tags: dict[str, str] = Field(default_factory=dict)
    wiki_title: str | None = None
    wiki_extract: str | None = None


class PreviousSelection(BaseModel):
    poi_id: str
    poi_name: str = ""
    script: str = ""


class NarrationRequest(BaseModel):
    candidates: list[POICandidate]
    persona: str = "history_uncle"
    lang: str = "zh-TW"
    length: str = "medium"
    force_regenerate: bool = False
    previous_selection: PreviousSelection | None = None


def get_narration_service() -> NarrationService:
    raise NotImplementedError("Override with dependency")


def get_persona_registry() -> dict[str, PersonaConfig]:
    raise NotImplementedError("Override with dependency")


def _event_to_dict(event) -> dict:
    d = dataclasses.asdict(event)
    d.pop("type", None)
    return d


@router.post("/narration")
async def narrate(
    request: NarrationRequest,
    narration_service: NarrationService = Depends(get_narration_service),  # noqa: B008
    persona_registry: dict = Depends(get_persona_registry),  # noqa: B008
):
    if request.persona not in persona_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: '{request.persona}'. "
            f"Valid options: {sorted(persona_registry.keys())}",
        )
    persona: PersonaConfig = persona_registry[request.persona]

    # Build POI context from frontend-provided data
    tags = dict(request.poi_tags)
    if request.poi_name and "name" not in tags:
        tags["name"] = request.poi_name

    wiki: WikiArticle | None = None
    if request.wiki_title and request.wiki_extract:
        wiki = WikiArticle(
            title=request.wiki_title,
            extract=request.wiki_extract,
            url=request.wiki_url or "",
            lang=request.wiki_lang or request.lang,
        )

    poi_context = POIContext(
        osm=OsmNode(id=request.poi_id, lat=request.poi_lat, lon=request.poi_lon, tags=tags),
        wiki=wiki,
    )
    logger.info(
        "narration request | poi_id=%s | poi_name=%s | has_wiki=%s",
        request.poi_id,
        tags.get("name", request.poi_id),
        wiki is not None,
    )

    async def generate():
        try:
            async for event in narration_service.narrate(
                poi=poi_context,
                persona=persona,
                lang=request.lang,
                length=request.length,
                force_regenerate=request.force_regenerate,
            ):
                event_type = event.type
                data = _event_to_dict(event)
                yield encode_event(event_type, data)
        except Exception as e:
            logger.exception("narration pipeline failed for poi_id=%s", request.poi_id)
            yield encode_event(
                "error",
                {"code": "internal_error", "message": str(e), "retry_after_s": 0},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
