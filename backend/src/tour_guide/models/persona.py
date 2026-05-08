from dataclasses import dataclass, field
from typing import Any


@dataclass
class VoiceStyle:
    speaking_rate: float = 1.0
    emotion: str = "neutral"


@dataclass
class StyleProfile:
    embellishment: float = 0.0
    preferred_topics: list[str] = field(default_factory=list)


@dataclass
class PersonaConfig:
    id: str
    display_name: dict[str, str]          # e.g. {"zh-TW": "歷史大叔", "en": "The History Uncle"}
    voice: dict[str, str]                 # e.g. {"zh-TW": "Charon", "en": "Charon"}
    voice_style: VoiceStyle
    style_profile: StyleProfile
    poi_source: str                        # e.g. "osm_wikipedia"
    system_prompt: dict[str, str]         # lang -> prompt text
    narration_template: dict[str, str]    # lang -> template text
    qa_template: dict[str, str]           # lang -> template text
    system_messages: dict[str, Any] = field(default_factory=dict)
    confidence_labels: dict[str, Any] = field(default_factory=dict)
