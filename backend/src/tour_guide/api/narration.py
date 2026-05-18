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
from tour_guide.services.poi_selector import POISelectorService

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


def get_poi_selector_service() -> POISelectorService:
    raise NotImplementedError("Override with dependency")


def _event_to_dict(event) -> dict:
    d = dataclasses.asdict(event)
    d.pop("type", None)
    return d


@router.post("/narration")
async def narrate(
    request: NarrationRequest,
    narration_service: NarrationService = Depends(get_narration_service),  # noqa: B008
    poi_selector: POISelectorService = Depends(get_poi_selector_service),  # noqa: B008
    persona_registry: dict = Depends(get_persona_registry),  # noqa: B008
):
    if not request.candidates:
        raise HTTPException(status_code=400, detail="candidates list must not be empty")
    if request.persona not in persona_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: '{request.persona}'. "
            f"Valid options: {sorted(persona_registry.keys())}",
        )
    persona: PersonaConfig = persona_registry[request.persona]

    # Step 1: LLM selects best POI from candidates
    selected_id = await poi_selector.select(
        candidates=request.candidates,
        persona=persona,
        lang=request.lang,
        previous=request.previous_selection,
    )

    # Step 2: If selector returned None, all candidates are trivial — stream skip event
    if selected_id is None:
        async def skip_stream():
            yield encode_event("skip", {"min_displacement_m": 1500.0})

        return StreamingResponse(
            skip_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Step 3: Find selected candidate and build POIContext
    selected = next((c for c in request.candidates if c.poi_id == selected_id), request.candidates[0])
    tags = dict(selected.poi_tags)
    if selected.poi_name and "name" not in tags:
        tags["name"] = selected.poi_name

    wiki: WikiArticle | None = None
    if selected.wiki_title and selected.wiki_extract:
        wiki = WikiArticle(
            title=selected.wiki_title,
            extract=selected.wiki_extract,
            url="",
            lang=request.lang,
        )

    poi_context = POIContext(
        osm=OsmNode(id=selected.poi_id, lat=selected.poi_lat, lon=selected.poi_lon, tags=tags),
        wiki=wiki,
        distance_m=selected.distance_m,
    )
    logger.info(
        "narration request | selected_poi_id=%s | poi_name=%s | has_wiki=%s | candidates=%d",
        selected.poi_id,
        tags.get("name", selected.poi_id),
        wiki is not None,
        len(request.candidates),
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
            logger.exception("narration pipeline failed for poi_id=%s", selected.poi_id)
            yield encode_event(
                "error",
                {"code": "internal_error", "message": str(e), "retry_after_s": 0},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
