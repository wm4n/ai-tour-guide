"""PersonaLoader: loads PersonaConfig from YAML files in prompts/personas/."""

from pathlib import Path
from typing import Any

import yaml

from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle

# Default base directory: backend/prompts/personas/
# This file lives at: src/tour_guide/prompts/loader.py
# So we go up 4 levels: loader.py -> prompts/ -> tour_guide/ -> src/ -> backend/
_DEFAULT_PERSONAS_DIR = Path(__file__).parent.parent.parent.parent / "prompts" / "personas"

_REQUIRED_FIELDS = (
    "id",
    "display_name",
    "voice",
    "voice_style",
    "style_profile",
    "poi_source",
    "system_prompt",
    "narration_template",
    "qa_template",
)


def _validate(data: dict[str, Any], path: Path) -> None:
    """Raise ValueError if any required field is missing."""
    missing = [f for f in _REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"Persona YAML at '{path}' is missing required field(s): {', '.join(missing)}"
        )


def _parse(data: dict[str, Any], path: Path) -> PersonaConfig:
    """Parse a raw YAML dict into a PersonaConfig, raising ValueError on bad data."""
    _validate(data, path)

    voice_style_data: dict[str, Any] = data.get("voice_style", {})
    voice_style = VoiceStyle(
        speaking_rate=float(voice_style_data.get("speaking_rate", 1.0)),
        emotion=str(voice_style_data.get("emotion", "neutral")),
    )

    style_profile_data: dict[str, Any] = data.get("style_profile", {})
    style_profile = StyleProfile(
        embellishment=float(style_profile_data.get("embellishment", 0.0)),
        preferred_topics=list(style_profile_data.get("preferred_topics", [])),
    )

    return PersonaConfig(
        id=data["id"],
        display_name=dict(data["display_name"]),
        voice=dict(data["voice"]),
        voice_style=voice_style,
        style_profile=style_profile,
        poi_source=str(data["poi_source"]),
        system_prompt=dict(data["system_prompt"]),
        narration_template=dict(data["narration_template"]),
        qa_template=dict(data["qa_template"]),
        system_messages=dict(data.get("system_messages") or {}),
        confidence_labels=dict(data.get("confidence_labels") or {}),
    )


class PersonaLoader:
    """Loads PersonaConfig instances from YAML files."""

    @classmethod
    def load(
        cls,
        persona_id: str,
        base_dir: Path = _DEFAULT_PERSONAS_DIR,
    ) -> PersonaConfig:
        """Load a persona by ID from ``{base_dir}/{persona_id}.yaml``.

        Raises:
            FileNotFoundError: if the YAML file does not exist.
            ValueError: if required fields are missing from the YAML.
        """
        path = base_dir / f"{persona_id}.yaml"
        if not path.exists():
            raise FileNotFoundError(
                f"Persona '{persona_id}' not found: '{path}' does not exist."
            )
        return cls.load_from_path(path)

    @classmethod
    def load_from_path(cls, path: Path) -> PersonaConfig:
        """Load a PersonaConfig from an explicit YAML file path.

        Raises:
            FileNotFoundError: if the file does not exist.
            ValueError: if required fields are missing.
        """
        if not path.exists():
            raise FileNotFoundError(f"Persona YAML not found: '{path}'")
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return _parse(data, path)
