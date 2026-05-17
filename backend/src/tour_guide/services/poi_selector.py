"""POISelectorService — uses LLM to select the most narratable POI from candidates."""
import logging

from tour_guide.log_events import LogEvents
from tour_guide.logging_config import log_event
from tour_guide.models.persona import PersonaConfig
from tour_guide.providers.llm import LlmOpts, LlmProvider, Message

logger = logging.getLogger(__name__)


class POISelectorService:
    """Non-streaming LLM call that picks the best POI id from a candidate list."""

    def __init__(self, llm: LlmProvider) -> None:
        self._llm = llm

    async def select(
        self,
        candidates,   # list[POICandidate] — imported at call site to avoid circular
        persona: PersonaConfig,
        lang: str,
        previous=None,  # PreviousSelection | None
    ) -> str | None:
        """Return poi_id of best candidate, or None if all candidates are trivial (SKIP)."""
        if not candidates:
            raise ValueError("candidates list is empty")

        candidate_lines = "\n".join(
            f"- [{c.poi_id}] {c.poi_name} ({c.distance_m:.0f}m)"
            f"{' [has Wikipedia]' if c.wiki_extract else ' [no Wikipedia]'}"
            for c in candidates
        )

        previous_section = ""
        if previous is not None:
            preview = previous.script[:400] + ("..." if len(previous.script) > 400 else "")
            previous_section = (
                f"\n\nPrevious narration:\n"
                f"POI: {previous.poi_name}\n"
                f"Script preview: {preview}"
            )

        user_content = (
            f"Select the single best POI to narrate for a {lang} tour guide "
            f"with persona '{persona.id}'.\n\n"
            f"Candidates:\n{candidate_lines}"
            f"{previous_section}\n\n"
            f"Rules:\n"
            f"- Prefer POIs with Wikipedia data\n"
            f"- Prefer closer POIs over farther ones when quality is similar\n"
            f"- Avoid choosing the same theme as the previous narration\n"
            f"- If ALL candidates are trivial (maps/signs/boards/bus stops with no Wikipedia), "
            f"reply with SKIP\n"
            f"- Trivial examples: names containing 地圖/map/導覽圖/公車/巴士/bus/signboard/"
            f"information board, AND no Wikipedia data\n"
            f"- Worth narrating: has Wikipedia data, OR is a named attraction/monument/"
            f"building/park/temple\n"
            f"- Reply with ONLY the poi_id or ONLY the word SKIP — nothing else"
        )

        messages = [
            Message(role="system", content="You are a tour guide POI selector. Output only the poi_id or SKIP."),
            Message(role="user", content=user_content),
        ]
        opts = LlmOpts(temperature=0.1, max_tokens=64)

        result = ""
        async for chunk in self._llm.chat_stream(messages, opts):
            result += chunk
        selected_id = result.strip()

        if selected_id == "SKIP":
            log_event(
                logger,
                LogEvents.POI_SELECTION_SKIP,
                candidate_count=len(candidates),
                has_previous=previous is not None,
            )
            return None

        valid_ids = {c.poi_id for c in candidates}
        if selected_id not in valid_ids:
            logger.warning(
                "POI selector returned invalid id '%s', falling back to first candidate", selected_id
            )
            selected_id = candidates[0].poi_id

        log_event(
            logger,
            LogEvents.POI_SELECTION,
            selected_id=selected_id,
            candidate_count=len(candidates),
            has_previous=previous is not None,
        )
        return selected_id
