"""Tests for PersonaLoader — TDD: write failing tests first."""

import pytest
import yaml

from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.prompts.loader import PersonaLoader


class TestPersonaLoaderLoad:
    """Tests for PersonaLoader.load()."""

    def test_load_history_uncle_returns_persona_config(self):
        """PersonaLoader.load('history_uncle') should return a PersonaConfig."""
        config = PersonaLoader.load("history_uncle")
        assert isinstance(config, PersonaConfig)

    def test_load_history_uncle_id(self):
        """Loaded PersonaConfig should have correct id."""
        config = PersonaLoader.load("history_uncle")
        assert config.id == "history_uncle"

    def test_load_history_uncle_display_name(self):
        """Loaded PersonaConfig should have correct display_name mapping."""
        config = PersonaLoader.load("history_uncle")
        assert config.display_name["zh-TW"] == "歷史大叔"
        assert config.display_name["en"] == "The History Uncle"

    def test_load_history_uncle_voice(self):
        """Loaded PersonaConfig should have correct voice mapping."""
        config = PersonaLoader.load("history_uncle")
        assert config.voice["zh-TW"] == "Charon"
        assert config.voice["en"] == "Charon"

    def test_load_history_uncle_voice_style(self):
        """Loaded PersonaConfig should have correct VoiceStyle."""
        config = PersonaLoader.load("history_uncle")
        assert isinstance(config.voice_style, VoiceStyle)
        assert config.voice_style.speaking_rate == 0.95
        assert config.voice_style.emotion == "contemplative"

    def test_load_history_uncle_style_profile(self):
        """Loaded PersonaConfig should have correct StyleProfile."""
        config = PersonaLoader.load("history_uncle")
        assert isinstance(config.style_profile, StyleProfile)
        assert config.style_profile.embellishment == 0.1
        assert "history" in config.style_profile.preferred_topics
        assert "cultural_context" in config.style_profile.preferred_topics

    def test_load_history_uncle_poi_source(self):
        """Loaded PersonaConfig should have correct poi_source."""
        config = PersonaLoader.load("history_uncle")
        assert config.poi_source == "osm_wikipedia"

    def test_load_history_uncle_system_prompt(self):
        """Loaded PersonaConfig should have system_prompt for both languages."""
        config = PersonaLoader.load("history_uncle")
        assert "zh-TW" in config.system_prompt
        assert "en" in config.system_prompt
        assert len(config.system_prompt["zh-TW"]) > 0
        assert len(config.system_prompt["en"]) > 0

    def test_load_history_uncle_narration_template(self):
        """Loaded PersonaConfig should have narration_template for both languages."""
        config = PersonaLoader.load("history_uncle")
        assert "zh-TW" in config.narration_template
        assert "en" in config.narration_template

    def test_load_history_uncle_qa_template(self):
        """Loaded PersonaConfig should have qa_template for both languages."""
        config = PersonaLoader.load("history_uncle")
        assert "zh-TW" in config.qa_template
        assert "en" in config.qa_template

    def test_load_history_uncle_system_messages(self):
        """Loaded PersonaConfig should have system_messages dict."""
        config = PersonaLoader.load("history_uncle")
        assert isinstance(config.system_messages, dict)
        assert "zh-TW" in config.system_messages

    def test_load_history_uncle_confidence_labels(self):
        """Loaded PersonaConfig should have confidence_labels dict."""
        config = PersonaLoader.load("history_uncle")
        assert isinstance(config.confidence_labels, dict)
        assert "zh-TW" in config.confidence_labels


class TestPersonaLoaderErrors:
    """Tests for PersonaLoader error handling."""

    def test_load_nonexistent_raises_file_not_found(self):
        """Loading a nonexistent persona should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            PersonaLoader.load("nonexistent")

    def test_load_missing_required_field_raises_value_error(self, tmp_path):
        """Loading YAML missing required field 'id' should raise ValueError."""
        invalid_yaml = {
            "display_name": {"zh-TW": "測試", "en": "Test"},
            "voice": {"zh-TW": "Charon", "en": "Charon"},
            "voice_style": {"speaking_rate": 1.0, "emotion": "neutral"},
            "style_profile": {"embellishment": 0.0, "preferred_topics": []},
            "poi_source": "osm_wikipedia",
            "system_prompt": {"zh-TW": "prompt", "en": "prompt"},
            "narration_template": {"zh-TW": "template", "en": "template"},
            "qa_template": {"zh-TW": "qa", "en": "qa"},
        }
        invalid_file = tmp_path / "no_id_persona.yaml"
        invalid_file.write_text(yaml.dump(invalid_yaml))

        with pytest.raises(ValueError, match="id"):
            PersonaLoader.load_from_path(invalid_file)


class TestPersonaLoaderLoadAll:
    """Tests for PersonaLoader.load_all()."""

    def test_load_all_returns_dict_with_history_uncle(self):
        """load_all() should include history_uncle (the only YAML that exists so far)."""
        registry = PersonaLoader.load_all()
        assert "history_uncle" in registry
        assert isinstance(registry["history_uncle"], PersonaConfig)

    def test_load_all_returns_dict_keyed_by_id(self):
        """load_all() should key each persona by its id field."""
        registry = PersonaLoader.load_all()
        for persona_id, config in registry.items():
            assert config.id == persona_id

    def test_load_all_custom_dir_empty(self, tmp_path):
        """load_all() on empty directory returns empty dict."""
        registry = PersonaLoader.load_all(base_dir=tmp_path)
        assert registry == {}

    def test_load_all_custom_dir_with_yaml(self, tmp_path):
        """load_all() loads all YAML files from given directory."""
        yaml_content = """
id: test_persona
display_name:
  zh-TW: 測試
  en: Test
voice:
  zh-TW: Charon
  en: Charon
voice_style:
  speaking_rate: 1.0
  emotion: neutral
style_profile:
  embellishment: 0.0
  preferred_topics: []
poi_source: osm_wikipedia
system_prompt:
  zh-TW: 測試 prompt
  en: Test prompt
narration_template:
  zh-TW: "narrate {poi_name}"
  en: "narrate {poi_name}"
qa_template:
  zh-TW: "answer {question}"
  en: "answer {question}"
"""
        (tmp_path / "test_persona.yaml").write_text(yaml_content)
        registry = PersonaLoader.load_all(base_dir=tmp_path)
        assert "test_persona" in registry
        assert len(registry) == 1
