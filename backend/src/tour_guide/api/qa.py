"""POST /qa — SSE streaming Q&A endpoint."""

import dataclasses
import json

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from tour_guide.api.sse import encode_event
from tour_guide.models.persona import PersonaConfig
from tour_guide.services.qa_service import QAService

router = APIRouter()


def get_qa_service() -> QAService:
    raise NotImplementedError("Override with dependency")


def get_persona_registry() -> dict[str, PersonaConfig]:
    raise NotImplementedError("Override with dependency")


def _event_to_dict(event) -> dict:
    d = dataclasses.asdict(event)
    d.pop("type", None)
    return d


@router.post("/qa")
async def qa_answer(
    audio: UploadFile,
    context: str = Form(...),
    qa_service: QAService = Depends(get_qa_service),  # noqa: B008
    persona_registry: dict = Depends(get_persona_registry),  # noqa: B008
):
    ctx = json.loads(context)
    persona_id = ctx.get("persona", "history_uncle")

    if persona_id not in persona_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: '{persona_id}'. Valid options: {sorted(persona_registry.keys())}",
        )

    persona: PersonaConfig = persona_registry[persona_id]
    lang = ctx.get("lang", "zh-TW")
    current_poi_id = ctx.get("current_poi_id")  # nullable
    narration_so_far = ctx.get("narration_so_far", "")

    # Resolve POI name from ID for the prompt (use ID as name if no lookup)
    current_poi_name = current_poi_id if current_poi_id else None

    audio_bytes = await audio.read()

    async def generate():
        try:
            async for event in qa_service.answer(
                audio_bytes=audio_bytes,
                persona=persona,
                lang=lang,
                current_poi_name=current_poi_name,
                narration_so_far=narration_so_far,
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
