"""POST /narration — SSE streaming endpoint for tour guide narration."""

import dataclasses

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tour_guide.api.sse import encode_event
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.models.poi import OsmNode, POIContext
from tour_guide.services.narration_service import NarrationService

router = APIRouter()


class NarrationRequest(BaseModel):
    poi_id: str
    persona: str = "history_uncle"
    lang: str = "zh-TW"
    length: str = "medium"
    force_regenerate: bool = False


def get_narration_service() -> NarrationService:
    raise NotImplementedError("Override with dependency")


def _event_to_dict(event) -> dict:
    d = dataclasses.asdict(event)
    d.pop("type", None)
    return d


@router.post("/narration")
async def narrate(
    request: NarrationRequest,
    narration_service: NarrationService = Depends(get_narration_service),  # noqa: B008
):
    # Build a minimal POIContext from poi_id
    poi_context = POIContext(osm=OsmNode(id=request.poi_id, lat=0.0, lon=0.0, tags={}))
    # Build a minimal persona (in full app, load from PersonaLoader)
    persona = PersonaConfig(
        id=request.persona,
        display_name={"zh-TW": request.persona},
        voice={"zh-TW": "Charon"},
        voice_style=VoiceStyle(),
        style_profile=StyleProfile(),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "You are a tour guide."},
        narration_template={"zh-TW": "Narrate {poi_name}."},
        qa_template={"zh-TW": "Answer: {question}"},
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
            yield encode_event(
                "error",
                {"code": "internal_error", "message": str(e), "retry_after_s": 0},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
