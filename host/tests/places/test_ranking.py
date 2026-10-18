import math

from buddy_host.places.models import Candidate, Location
from buddy_host.places.ranking import rank, theme_of

HERE = Location(lat=25.0550, lon=121.5100, heading_deg=0.0)  # 面向北


def at(name: str, north_m: float = 0, east_m: float = 0, *, tags=None, wiki=False, id=None):
    return Candidate(
        id=id or f"osm:node:{name}",
        name=name,
        lat=HERE.lat + north_m / 111_195,
        lon=HERE.lon + east_m / (111_195 * math.cos(math.radians(HERE.lat))),
        tags={k: v for k, v in {"tourism": "attraction", **(tags or {})}.items() if v},
        wiki_title=name if wiki else None,
        wiki_extract="摘要" if wiki else None,
    )


def names(ranked):
    return [r.candidate.name for r in ranked]


def test_closer_beats_farther_when_otherwise_equal():
    ranked = rank([at("遠", 400), at("近", 100)], HERE, limit=2)

    assert names(ranked) == ["近", "遠"]


def test_ahead_beats_behind_at_the_same_distance():
    ranked = rank([at("後方", -200), at("前方", 200)], HERE, limit=2)

    assert names(ranked) == ["前方", "後方"]


def test_wikipedia_entry_beats_a_slightly_closer_plain_place():
    ranked = rank([at("普通", 150), at("有條目", 250, wiki=True)], HERE, limit=2)

    assert names(ranked)[0] == "有條目"


def test_unknown_heading_ignores_direction():
    still = Location(HERE.lat, HERE.lon, heading_deg=None)

    ranked = rank([at("後方近", -100), at("前方遠", 300)], still, limit=2)

    assert names(ranked) == ["後方近", "前方遠"]


def test_second_pick_prefers_a_different_theme():
    temple_a = at("廟甲", 100, tags={"tourism": None, "amenity": "place_of_worship"}, wiki=True)
    temple_b = at("廟乙", 120, tags={"tourism": None, "amenity": "place_of_worship"}, wiki=True)
    museum = at("博物館", 200, tags={"tourism": "museum"}, wiki=True)

    ranked = rank([temple_a, temple_b, museum], HERE, limit=2)

    assert names(ranked) == ["廟甲", "博物館"]


def test_recently_used_themes_are_demoted():
    temple = at("廟", 100, tags={"tourism": None, "amenity": "place_of_worship"}, wiki=True)
    museum = at("博物館", 150, tags={"tourism": "museum"}, wiki=True)

    ranked = rank([temple, museum], HERE, limit=1, recent_themes={theme_of(temple)})

    assert names(ranked) == ["博物館"]


def test_nameless_and_excluded_candidates_are_dropped():
    nameless = at("", 10)
    told = at("講過了", 20, id="osm:node:told")

    ranked = rank([nameless, told, at("可以", 300)], HERE, limit=3, exclude_ids={"osm:node:told"})

    assert names(ranked) == ["可以"]


def test_places_beyond_the_radius_are_dropped():
    assert rank([at("太遠", 900)], HERE, limit=3, radius_m=500) == []


def test_old_shop_with_a_story_is_eligible_but_plain_shop_is_not():
    story = at("老茶行", 100, tags={"tourism": None, "shop": "tea", "start_date": "1890"})
    plain = at("便利商店", 50, tags={"tourism": None, "shop": "convenience"})

    ranked = rank([story, plain], HERE, limit=3)

    assert names(ranked) == ["老茶行"]


def test_limit_caps_the_result_and_scores_are_exposed():
    ranked = rank([at(f"p{i}", 50 * i + 50) for i in range(5)], HERE, limit=2)

    assert len(ranked) == 2
    assert ranked[0].score >= ranked[1].score


def test_theme_of_uses_the_most_specific_tag():
    assert theme_of(at("a", tags={"tourism": "museum"})) == "tourism=museum"
    assert theme_of(at("b", tags={"tourism": None, "historic": "monument"})) == "historic=monument"


def test_wiki_title_alone_counts_as_having_a_wikipedia_entry():
    plain = at("普通", 150)
    titled = at("有標題", 250)
    titled = Candidate(**{**titled.__dict__, "wiki_title": "有標題"})

    ranked = rank([plain, titled], HERE, limit=2)

    assert names(ranked)[0] == "有標題"
