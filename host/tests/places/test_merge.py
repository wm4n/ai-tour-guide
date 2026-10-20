from buddy_host.places.merge import merge_wiki_hits
from buddy_host.places.models import Candidate
from buddy_host.places.wikipedia import WikiHit


def osm(name, lat=25.0554, lon=121.5099, **kw):
    return Candidate(f"osm:node:{name}", name, lat, lon, {"tourism": "attraction"}, **kw)


def test_hit_with_the_same_name_nearby_sets_the_wiki_title():
    merged = merge_wiki_hits([osm("霞海城隍廟")], [WikiHit("霞海城隍廟", 25.0555, 121.5099)])

    assert [(c.name, c.wiki_title) for c in merged] == [("霞海城隍廟", "霞海城隍廟")]


def test_title_containing_the_osm_name_matches():
    merged = merge_wiki_hits([osm("霞海城隍廟")], [WikiHit("台北霞海城隍廟", 25.0555, 121.5099)])

    assert merged[0].wiki_title == "台北霞海城隍廟"
    assert len(merged) == 1


def test_far_away_hit_with_same_name_does_not_match_and_becomes_its_own_candidate():
    merged = merge_wiki_hits([osm("廟")], [WikiHit("廟", 25.09, 121.55)])

    assert len(merged) == 2
    assert merged[0].wiki_title is None
    assert merged[1].id == "wiki:廟"


def test_unmatched_hit_becomes_a_new_attraction_candidate():
    merged = merge_wiki_hits([], [WikiHit("迪化街", 25.06, 121.51)])

    [new] = merged
    assert (new.id, new.name, new.wiki_title) == ("wiki:迪化街", "迪化街", "迪化街")
    assert new.tags["tourism"] == "attraction"


def test_existing_wiki_title_is_kept():
    merged = merge_wiki_hits(
        [osm("霞海城隍廟", wiki_title="原本的")], [WikiHit("霞海城隍廟", 25.0555, 121.5099)]
    )

    assert merged[0].wiki_title == "原本的"


def test_one_character_names_never_match_by_containment():
    merged = merge_wiki_hits([osm("廟")], [WikiHit("霞海城隍廟", 25.0555, 121.5099)])

    assert merged[0].wiki_title is None
    assert len(merged) == 2
