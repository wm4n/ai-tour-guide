from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.models.poi import POI, BBox, OsmNode, POIContext, Place, TagFilter, WikiArticle


class TestOsmNode:
    def test_osmnode_creation_with_all_fields(self):
        node = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
            tags={"name": "Taipei 101", "tourism": "attraction"},
        )
        assert node.id == "osm:node:12345"
        assert node.lat == 25.0455
        assert node.lon == 121.5681
        assert node.tags == {"name": "Taipei 101", "tourism": "attraction"}

    def test_osmnode_creation_without_tags(self):
        node = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        assert node.id == "osm:node:12345"
        assert node.lat == 25.0455
        assert node.lon == 121.5681
        assert node.tags == {}


class TestWikiArticle:
    def test_wikiarticle_creation(self):
        article = WikiArticle(
            title="Taipei 101",
            extract="Taipei 101 is the tallest structure in Taiwan.",
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        assert article.title == "Taipei 101"
        assert article.extract == "Taipei 101 is the tallest structure in Taiwan."
        assert article.url == "https://en.wikipedia.org/wiki/Taipei_101"
        assert article.lang == "en"


class TestPOI:
    def test_poi_creation_with_defaults(self):
        poi = POI(
            id="poi:1",
            name="Taipei 101",
            lat=25.0455,
            lon=121.5681,
        )
        assert poi.id == "poi:1"
        assert poi.name == "Taipei 101"
        assert poi.lat == 25.0455
        assert poi.lon == 121.5681
        assert poi.tags == {}
        assert poi.wiki is None
        assert poi.distance_m == 0.0
        assert poi.confidence == "low"

    def test_poi_creation_with_all_fields(self):
        wiki = WikiArticle(
            title="Taipei 101",
            extract="Taipei 101 is the tallest structure in Taiwan.",
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        poi = POI(
            id="poi:1",
            name="Taipei 101",
            lat=25.0455,
            lon=121.5681,
            tags={"tourism": "attraction"},
            wiki=wiki,
            distance_m=500.0,
            confidence="high",
        )
        assert poi.id == "poi:1"
        assert poi.name == "Taipei 101"
        assert poi.distance_m == 500.0
        assert poi.confidence == "high"
        assert poi.wiki == wiki
        assert poi.tags == {"tourism": "attraction"}

    def test_poi_default_distance_is_zero(self):
        poi = POI(id="poi:1", name="Test POI", lat=0.0, lon=0.0)
        assert poi.distance_m == 0.0

    def test_poi_default_confidence_is_low(self):
        poi = POI(id="poi:1", name="Test POI", lat=0.0, lon=0.0)
        assert poi.confidence == "low"


class TestBBox:
    def test_bbox_creation(self):
        bbox = BBox(
            min_lat=25.0,
            min_lon=121.5,
            max_lat=25.1,
            max_lon=121.6,
        )
        assert bbox.min_lat == 25.0
        assert bbox.min_lon == 121.5
        assert bbox.max_lat == 25.1
        assert bbox.max_lon == 121.6


class TestPOIContext:
    def test_poicontext_with_wiki(self):
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        wiki = WikiArticle(
            title="Taipei 101",
            extract="Taipei 101 is the tallest structure in Taiwan.",
            url="https://en.wikipedia.org/wiki/Taipei_101",
            lang="en",
        )
        context = POIContext(osm=osm, wiki=wiki)
        assert context.osm == osm
        assert context.wiki == wiki

    def test_poicontext_without_wiki(self):
        osm = OsmNode(
            id="osm:node:12345",
            lat=25.0455,
            lon=121.5681,
        )
        context = POIContext(osm=osm)
        assert context.osm == osm
        assert context.wiki is None


class TestPlaceModel:
    def test_place_has_required_fields(self):
        place = Place(
            id="gplace:ChIJ123",
            name="鼎泰豐",
            lat=25.033,
            lon=121.564,
            rating=4.6,
            user_ratings_total=328,
            price_level=2,
            types=["restaurant", "food"],
            vicinity="信義區松高路12號",
        )
        assert place.id == "gplace:ChIJ123"
        assert place.rating == 4.6
        assert place.price_level == 2

    def test_place_nullable_fields(self):
        place = Place(
            id="gplace:abc",
            name="無評分餐廳",
            lat=25.0,
            lon=121.0,
            rating=None,
            user_ratings_total=None,
            price_level=None,
            types=["restaurant"],
            vicinity="台北市",
        )
        assert place.rating is None
        assert place.user_ratings_total is None


class TestTagFilter:
    def test_tagfilter_with_values(self):
        tag_filter = TagFilter(
            key="tourism",
            values=["attraction", "museum"],
        )
        assert tag_filter.key == "tourism"
        assert tag_filter.values == ["attraction", "museum"]

    def test_tagfilter_without_values(self):
        tag_filter = TagFilter(key="tourism")
        assert tag_filter.key == "tourism"
        assert tag_filter.values == []


class TestVoiceStyle:
    def test_voicestyle_creation_with_defaults(self):
        voice = VoiceStyle()
        assert voice.speaking_rate == 1.0
        assert voice.emotion == "neutral"

    def test_voicestyle_creation_with_custom_values(self):
        voice = VoiceStyle(speaking_rate=1.2, emotion="enthusiastic")
        assert voice.speaking_rate == 1.2
        assert voice.emotion == "enthusiastic"


class TestStyleProfile:
    def test_styleprofile_creation_with_defaults(self):
        profile = StyleProfile()
        assert profile.embellishment == 0.0
        assert profile.preferred_topics == []

    def test_styleprofile_creation_with_custom_values(self):
        profile = StyleProfile(
            embellishment=0.5,
            preferred_topics=["history", "architecture"],
        )
        assert profile.embellishment == 0.5
        assert profile.preferred_topics == ["history", "architecture"]


class TestPersonaConfig:
    def test_personaconfig_creation(self):
        voice_style = VoiceStyle(speaking_rate=1.1, emotion="friendly")
        style_profile = StyleProfile(
            embellishment=0.3,
            preferred_topics=["history"],
        )
        persona = PersonaConfig(
            id="persona:1",
            display_name={"zh-TW": "歷史大叔", "en": "The History Uncle"},
            voice={"zh-TW": "Charon", "en": "Charon"},
            voice_style=voice_style,
            style_profile=style_profile,
            poi_source="osm_wikipedia",
            system_prompt={"zh-TW": "你是一個歷史導遊", "en": "You are a history guide"},
            narration_template={"zh-TW": "模板", "en": "template"},
            qa_template={"zh-TW": "問答模板", "en": "qa template"},
        )
        assert persona.id == "persona:1"
        assert persona.display_name == {"zh-TW": "歷史大叔", "en": "The History Uncle"}
        assert persona.voice == {"zh-TW": "Charon", "en": "Charon"}
        assert persona.voice_style == voice_style
        assert persona.style_profile == style_profile
        assert persona.poi_source == "osm_wikipedia"
        assert persona.system_prompt == {
            "zh-TW": "你是一個歷史導遊",
            "en": "You are a history guide",
        }
        assert persona.narration_template == {"zh-TW": "模板", "en": "template"}
        assert persona.qa_template == {"zh-TW": "問答模板", "en": "qa template"}
        assert persona.system_messages == {}
        assert persona.confidence_labels == {}

    def test_personaconfig_with_system_messages_and_labels(self):
        voice_style = VoiceStyle()
        style_profile = StyleProfile()
        persona = PersonaConfig(
            id="persona:1",
            display_name={"zh-TW": "歷史大叔"},
            voice={"zh-TW": "Charon"},
            voice_style=voice_style,
            style_profile=style_profile,
            poi_source="osm_wikipedia",
            system_prompt={"zh-TW": "你是一個歷史導遊"},
            narration_template={"zh-TW": "模板"},
            qa_template={"zh-TW": "問答模板"},
            system_messages={"key": "value"},
            confidence_labels={"high": "確信"},
        )
        assert persona.system_messages == {"key": "value"}
        assert persona.confidence_labels == {"high": "確信"}
