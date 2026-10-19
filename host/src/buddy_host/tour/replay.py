"""重播用的準備器：直接拿先前做好的介紹（*.meta.json＋*.wav），不呼叫 Claude、不合成。

用來在桌上把 App 的整條流程（時機、下載、播放、暫停）跑通，不消耗 Claude 額度。
"""

import json
from collections.abc import Callable, Collection
from pathlib import Path

from buddy_host.narration.preparer import PreparedNarration
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.geo import haversine_m
from buddy_host.places.models import Location


class ReplayPreparer:
    def __init__(self, directory: Path, *, radius_m: float = 600.0, limit: int = 2):
        self._directory = directory
        self._radius_m = radius_m
        self._limit = limit

    async def prepare(
        self,
        location: Location,
        *,
        exclude_ids: Collection[str] = (),
        traveler: TravelerContext | None = None,
        on_ready: Callable[[PreparedNarration], None] | None = None,
    ) -> list[PreparedNarration]:
        found: list[tuple[float, PreparedNarration]] = []
        for meta_path in sorted(self._directory.glob("*.meta.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            wav = meta_path.with_name(meta_path.name.removesuffix(".meta.json") + ".wav")
            if meta["candidate_id"] in exclude_ids or not wav.exists():
                continue
            distance = haversine_m(location.lat, location.lon, meta["lat"], meta["lon"])
            if distance > self._radius_m:
                continue
            found.append(
                (
                    distance,
                    PreparedNarration(
                        meta["candidate_id"],
                        meta["name"],
                        meta["script"],
                        wav,
                        meta_path,
                        meta["audio_seconds"],
                        round(distance, 1),
                        meta["lat"],
                        meta["lon"],
                    ),
                )
            )
        found.sort(key=lambda pair: pair[0])
        return [item for _, item in found[: self._limit]]
