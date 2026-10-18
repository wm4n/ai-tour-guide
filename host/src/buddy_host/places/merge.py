from collections.abc import Sequence
from dataclasses import replace

from buddy_host.places.geo import haversine_m
from buddy_host.places.models import Candidate
from buddy_host.places.wikipedia import WikiHit

MATCH_DISTANCE_M = 150.0
MIN_CONTAINMENT_CHARS = 2


def names_match(name: str, title: str) -> bool:
    if name == title:
        return True
    if min(len(name), len(title)) < MIN_CONTAINMENT_CHARS:
        return False
    return name in title or title in name


def merge_wiki_hits(candidates: Sequence[Candidate], hits: Sequence[WikiHit]) -> list[Candidate]:
    """把 Wikipedia 座標搜尋的結果對到 OSM 物件上；對不到的當成新的景點。"""
    merged = list(candidates)
    for hit in hits:
        for i, candidate in enumerate(merged):
            close = haversine_m(candidate.lat, candidate.lon, hit.lat, hit.lon) <= MATCH_DISTANCE_M
            if close and names_match(candidate.name, hit.title):
                if candidate.wiki_title is None:
                    merged[i] = replace(candidate, wiki_title=hit.title)
                break
        else:
            merged.append(
                Candidate(
                    id=f"wiki:{hit.title}",
                    name=hit.title,
                    lat=hit.lat,
                    lon=hit.lon,
                    tags={"tourism": "attraction"},
                    wiki_title=hit.title,
                )
            )
    return merged
