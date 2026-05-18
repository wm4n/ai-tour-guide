"""Tests for PromptBuilder — TDD: write failing tests first."""

import pytest

from tour_guide.models.poi import OsmNode, POIContext, WikiArticle
from tour_guide.prompts.builder import PromptBuilder
from tour_guide.prompts.loader import PersonaLoader


class TestPromptBuilderBuild:
    """Tests for PromptBuilder.build()."""

    @pytest.fixture
    def history_uncle_persona(self):
        """Load history_uncle persona for testing."""
        return PersonaLoader.load("history_uncle")

    @pytest.fixture
    def poi_with_wiki(self):
        """Create a POIContext with OSM node and wiki article."""
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0338,
            lon=121.5645,
            tags={"name": "國立故宮博物院", "tourism": "museum"},
        )
        wiki = WikiArticle(
            title="National Palace Museum",
            extract="The National Palace Museum is a museum in Taipei, Taiwan. "
            "It is one of the largest museums of Chinese art in the world.",
            url="https://en.wikipedia.org/wiki/National_Palace_Museum",
            lang="en",
        )
        return POIContext(osm=osm, wiki=wiki)

    @pytest.fixture
    def poi_without_wiki(self):
        """Create a POIContext without wiki article."""
        osm = OsmNode(
            id="osm:node:67890",
            lat=25.0338,
            lon=121.5645,
            tags={"name": "某個景點"},
        )
        return POIContext(osm=osm, wiki=None)

    def test_build_returns_list_of_dicts(self, history_uncle_persona, poi_with_wiki):
        """PromptBuilder.build() should return a list of message dicts."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="medium",
        )
        assert isinstance(messages, list)
        assert len(messages) >= 2

    def test_build_has_system_and_user_messages(self, history_uncle_persona, poi_with_wiki):
        """Return value must contain at least one system and one user message."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="medium",
        )
        system_messages = [m for m in messages if m.get("role") == "system"]
        user_messages = [m for m in messages if m.get("role") == "user"]

        assert len(system_messages) >= 1
        assert len(user_messages) >= 1
        assert all(isinstance(m.get("content"), str) for m in system_messages)
        assert all(isinstance(m.get("content"), str) for m in user_messages)

    def test_build_poi_name_in_user_message(self, history_uncle_persona, poi_with_wiki):
        """POI name should appear in the user message."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="medium",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        assert "國立故宮博物院" in user_content

    def test_build_wiki_extract_included(self, history_uncle_persona, poi_with_wiki):
        """Wiki extract should be included when poi_context.wiki is not None."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="medium",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        # The wiki extract should be present in the user message
        assert "National Palace Museum" in user_content or "museum" in user_content

    def test_build_wiki_extract_truncated_to_1500_chars(self, history_uncle_persona):
        """Wiki extract should be truncated to max 1500 chars when longer."""
        long_extract = "x" * 2000  # Create an extract longer than 1500 chars
        osm = OsmNode(
            id="osm:node:99999",
            lat=25.0338,
            lon=121.5645,
            tags={"name": "長文章景點"},
        )
        wiki = WikiArticle(
            title="Long Article",
            extract=long_extract,
            url="https://example.com",
            lang="en",
        )
        poi = POIContext(osm=osm, wiki=wiki)

        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi,
            lang="zh-TW",
            length="medium",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        # Count consecutive x's to verify truncation
        max_consecutive_x = len(max(user_content.split("x")))
        assert max_consecutive_x <= 1501  # Allow 1 extra for safety

    def test_build_without_wiki_shows_fallback_message(
        self, history_uncle_persona, poi_without_wiki
    ):
        """Should show fallback message when wiki is None."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_without_wiki,
            lang="zh-TW",
            length="medium",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        # Should contain fallback message for no wiki data
        assert "無維基百科資料" in user_content or "(無維基百科資料)" in user_content

    def test_build_target_length_short(self, history_uncle_persona, poi_with_wiki):
        """Length 'short' should map to '100' in template."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="short",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        assert "100" in user_content

    def test_build_target_length_medium(self, history_uncle_persona, poi_with_wiki):
        """Length 'medium' should map to '200' in template."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="medium",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        assert "200" in user_content

    def test_build_target_length_long(self, history_uncle_persona, poi_with_wiki):
        """Length 'long' should map to '350' in template."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="long",
        )
        user_messages = [m for m in messages if m.get("role") == "user"]
        user_content = " ".join(m.get("content", "") for m in user_messages)

        assert "350" in user_content

    def test_build_system_message_from_persona(self, history_uncle_persona, poi_with_wiki):
        """System message should come from persona.system_prompt[lang]."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="zh-TW",
            length="medium",
        )
        system_messages = [m for m in messages if m.get("role") == "system"]
        system_content = system_messages[0].get("content", "")

        # Should contain text from the system prompt (first-person, no third-person role label)
        assert "歷史" in system_content or "台灣" in system_content
        assert "繁體中文" in system_content

    def test_build_english_language(self, history_uncle_persona, poi_with_wiki):
        """Should work with English language."""
        messages = PromptBuilder.build(
            persona=history_uncle_persona,
            poi=poi_with_wiki,
            lang="en",
            length="medium",
        )
        system_messages = [m for m in messages if m.get("role") == "system"]
        system_content = system_messages[0].get("content", "")

        # English system prompt should be used
        assert "History Uncle" in system_content or "English" in system_content


class TestPromptBuilderQA:
    """Tests for PromptBuilder.build_qa()."""

    @pytest.fixture
    def persona(self):
        from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
        return PersonaConfig(
            id="history_uncle",
            display_name={"zh-TW": "歷史大叔"},
            voice={"zh-TW": "Charon"},
            voice_style=VoiceStyle(),
            style_profile=StyleProfile(),
            poi_source="osm_wikipedia",
            system_prompt={"zh-TW": "你是歷史大叔。"},
            narration_template={"zh-TW": "narrate {poi_name}"},
            qa_template={
                "zh-TW": "{system_prompt}\n使用者在「{poi_name}」附近，旁白摘要：{narration_summary}\n使用者問：「{user_question}」",
                "en": "{system_prompt}\nUser is near '{poi_name}'. Summary: {narration_summary}\nQuestion: '{user_question}'",
            },
        )

    def test_build_qa_with_poi(self, persona):
        messages = PromptBuilder.build_qa(
            persona=persona,
            lang="zh-TW",
            current_poi_name="故宮博物院",
            narration_so_far="故宮是台灣最重要的博物館...",
            user_question="這裡有多少文物？",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "歷史大叔" in messages[0]["content"]
        user_msg = messages[1]["content"]
        assert "故宮博物院" in user_msg
        assert "這裡有多少文物？" in user_msg

    def test_build_qa_without_poi(self, persona):
        messages = PromptBuilder.build_qa(
            persona=persona,
            lang="zh-TW",
            current_poi_name=None,
            narration_so_far="",
            user_question="台北有什麼好玩的？",
        )
        assert len(messages) == 2
        user_msg = messages[1]["content"]
        assert "台北有什麼好玩的？" in user_msg

    def test_build_qa_english(self, persona):
        messages = PromptBuilder.build_qa(
            persona=persona,
            lang="en",
            current_poi_name="National Palace Museum",
            narration_so_far="The museum holds...",
            user_question="How old is it?",
        )
        assert "How old is it?" in messages[1]["content"]
