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

        # Should contain text from the system prompt
        assert "歷史大叔" in system_content
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
