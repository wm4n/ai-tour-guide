"""景點排序：行進方向前方、有 Wikipedia 條目、距離近、主題不重複（設計文件第 7 節）。"""

from collections.abc import Collection
from dataclasses import dataclass

from buddy_host.places.geo import angle_diff, bearing_deg, haversine_m
from buddy_host.places.models import Candidate, Location

DEFAULT_RADIUS_M = 500.0

_W_DISTANCE = 1.0
_W_DIRECTION = 0.35
_W_WIKI = 0.35
_W_STORY = 0.15
_THEME_PENALTY = 0.5
_MIN_DIRECTION_DISTANCE_M = 15.0  # 太近時方位角沒有意義

_THEME_KEYS = ("tourism", "historic", "amenity", "shop", "craft")
_STORY_KEYS = ("wikidata", "wikipedia", "heritage", "start_date")
_ALWAYS_ELIGIBLE_KEYS = ("tourism", "historic")
# 沒有觀光／古蹟標籤時，這些標籤代表行政區、道路、車站，不是景點（真實資料：「延平」是行政區標籤）
_NOT_ATTRACTION_KEYS = ("place", "boundary", "highway", "railway", "public_transport")
# 街邊設施常帶品牌的 wikidata（真實資料：以故居命名的 YouBike 站），不是有故事的店
_INFRASTRUCTURE_AMENITIES = frozenset({
    "bicycle_rental", "bicycle_parking", "parking", "parking_entrance", "bench", "toilets",
    "drinking_water", "bus_station", "taxi", "atm", "bank", "post_box", "vending_machine",
    "charging_station", "waste_basket", "recycling", "shelter", "fuel", "motorcycle_parking",
})  # fmt: skip


@dataclass(frozen=True)
class Ranked:
    candidate: Candidate
    score: float
    distance_m: float
    bearing_deg: float


def theme_of(candidate: Candidate) -> str:
    for key in _THEME_KEYS:
        if value := candidate.tags.get(key):
            return f"{key}={value}"
    return "other"


def _same_place(a: Candidate, b: Candidate) -> bool:
    if a.name == b.name:
        return True
    return a.wiki_title is not None and a.wiki_title == b.wiki_title


def _has_story(candidate: Candidate) -> bool:
    return any(candidate.tags.get(key) for key in _STORY_KEYS)


def _eligible(candidate: Candidate) -> bool:
    if not candidate.name.strip():
        return False
    tags = candidate.tags
    if tags.get("amenity") in _INFRASTRUCTURE_AMENITIES:
        return False
    if any(tags.get(key) for key in _ALWAYS_ELIGIBLE_KEYS):
        return True
    if any(tags.get(key) for key in _NOT_ATTRACTION_KEYS):
        return False
    if tags.get("amenity") == "place_of_worship":
        return True
    # 有故事的老店、知名店家：沒有觀光／古蹟標籤，但有年代、遺產或維基標記
    return _has_story(candidate)


def _direction_score(location: Location, target_bearing: float, distance_m: float) -> float:
    if location.heading_deg is None or distance_m < _MIN_DIRECTION_DISTANCE_M:
        return 0.0
    diff = angle_diff(location.heading_deg, target_bearing)
    return max(-1.0, min(1.0, (90 - diff) / 90))  # 正前方 +1、側面 0、正後方 −1


def rank(
    candidates: Collection[Candidate],
    location: Location,
    *,
    limit: int,
    radius_m: float = DEFAULT_RADIUS_M,
    exclude_ids: Collection[str] = (),
    recent_themes: Collection[str] = (),
) -> list[Ranked]:
    scored: list[Ranked] = []
    for candidate in candidates:
        if candidate.id in exclude_ids or not _eligible(candidate):
            continue
        distance = haversine_m(location.lat, location.lon, candidate.lat, candidate.lon)
        if distance > radius_m:
            continue
        bearing = bearing_deg(location.lat, location.lon, candidate.lat, candidate.lon)
        score = (
            _W_DISTANCE * (1 - distance / radius_m)
            + _W_DIRECTION * _direction_score(location, bearing, distance)
            + (_W_WIKI if candidate.wiki_title or candidate.wiki_extract else 0.0)
            + (_W_STORY if _has_story(candidate) else 0.0)
        )
        scored.append(Ranked(candidate, score, distance, bearing))

    # 貪婪挑選：已挑過或最近講過的主題扣分，讓同一趟的主題不重複
    chosen: list[Ranked] = []
    used_themes = set(recent_themes)
    remaining = list(scored)
    while remaining and len(chosen) < limit:

        def adjusted(r: Ranked) -> float:
            penalty = _THEME_PENALTY if theme_of(r.candidate) in used_themes else 0.0
            return r.score - penalty

        best = max(remaining, key=adjusted)
        # 同名或同一個維基條目只佔一個名額（同一個地方常同時有 way 與 node）
        remaining = [r for r in remaining if not _same_place(r.candidate, best.candidate)]
        chosen.append(Ranked(best.candidate, adjusted(best), best.distance_m, best.bearing_deg))
        used_themes.add(theme_of(best.candidate))
    return chosen
