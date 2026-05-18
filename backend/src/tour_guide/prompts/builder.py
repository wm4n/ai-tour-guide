"""PromptBuilder — pure function for building LLM prompts from personas and POIs."""

from typing import ClassVar

from tour_guide.models.persona import PersonaConfig
from tour_guide.models.poi import POIContext


class PromptBuilder:
    """Build prompts for LLM narration from persona and POI context."""

    # Length mapping
    LENGTH_TO_WORD_COUNT: ClassVar[dict[str, str]] = {
        "short": "100",
        "medium": "200",
        "long": "350",
    }

    DISTANCE_HINTS: ClassVar[dict[str, list[tuple[float, str]]]] = {
        "zh-TW": [
            (30.0, "就在你附近"),
            (150.0, "前方不遠處"),
            (500.0, "這附近"),
            (float("inf"), "這一帶"),
        ],
        "en": [
            (30.0, "right here"),
            (150.0, "not far ahead"),
            (500.0, "nearby"),
            (float("inf"), "in this area"),
        ],
    }

    @staticmethod
    def _distance_hint(distance_m: float, lang: str) -> str:
        bins = PromptBuilder.DISTANCE_HINTS.get(lang, PromptBuilder.DISTANCE_HINTS["en"])
        for threshold, label in bins:
            if distance_m < threshold:
                return label
        return bins[-1][1]

    @staticmethod
    def build(
        persona: PersonaConfig,
        poi: POIContext,
        lang: str,
        length: str,
    ) -> list[dict]:
        """
        Build a list of messages for LLM prompt.

        Args:
            persona: PersonaConfig with system_prompt and narration_template
            poi: POIContext with OSM node and optional wiki article
            lang: Language code (e.g. "zh-TW", "en")
            length: Length preference ("short" | "medium" | "long")

        Returns:
            List of message dicts with system and user messages.
        """
        # Extract POI name
        poi_name = poi.osm.tags.get("name", poi.osm.id)

        # Prepare POI context string
        if poi.wiki:
            # Truncate wiki extract to max 1500 chars
            wiki_extract = poi.wiki.extract[:1500]
            poi_context_str = wiki_extract
        else:
            # Fallback message when no wiki data
            poi_context_str = "(無維基百科資料)"

        # Get target length word count
        target_length = PromptBuilder.LENGTH_TO_WORD_COUNT.get(length, "200")

        # Get templates from persona
        system_prompt_text = persona.system_prompt.get(lang, "")
        narration_template_text = persona.narration_template.get(lang, "")

        # Compute distance hint from POI context
        distance_hint = PromptBuilder._distance_hint(poi.distance_m, lang)

        # Fill in narration template variables
        user_prompt_text = narration_template_text.format(
            poi_name=poi_name,
            poi_context=poi_context_str,
            target_length=target_length,
            distance_hint=distance_hint,
        )

        # Build message list
        messages = [
            {"role": "system", "content": system_prompt_text},
            {"role": "user", "content": user_prompt_text},
        ]

        return messages

    @staticmethod
    def build_qa(
        persona: PersonaConfig,
        lang: str,
        current_poi_name: str | None,
        narration_so_far: str,
        user_question: str,
    ) -> list[dict]:
        """Build messages for Q&A LLM prompt.

        Args:
            persona: PersonaConfig with system_prompt and qa_template
            lang: Language code (e.g. "zh-TW", "en")
            current_poi_name: Name of current POI, or None if no narration active
            narration_so_far: Accumulated narration subtitle text
            user_question: Transcribed user question

        Returns:
            List of message dicts with system and user messages.
        """
        system_prompt_text = persona.system_prompt.get(lang, "")
        qa_template_text = persona.qa_template.get(lang, "")

        if current_poi_name:
            user_prompt_text = qa_template_text.format(
                system_prompt=system_prompt_text,
                poi_name=current_poi_name,
                narration_summary=narration_so_far[:500] if narration_so_far else "(無旁白摘要)",
                user_question=user_question,
            )
        else:
            # No POI context — general Q&A
            general_prompt = (
                f"{system_prompt_text}\n使用者沒有特定景點，請以你的口吻自然回答：「{user_question}」"
                if lang == "zh-TW"
                else f"{system_prompt_text}\nUser asks without a specific POI context: '{user_question}'"
            )
            user_prompt_text = general_prompt

        return [
            {"role": "system", "content": system_prompt_text},
            {"role": "user", "content": user_prompt_text},
        ]
