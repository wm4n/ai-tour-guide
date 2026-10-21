"""重播用的準備器：直接拿先前做好的介紹（*.meta.json＋*.wav），不呼叫 Claude、不合成。

音檔可以和 meta 平放（舊格式），也可以放在底下依聲音分開的資料夾（`<聲音鍵>/<名稱>.wav`）。

用來在桌上把 App 的整條流程（時機、下載、播放、暫停）跑通，不消耗 Claude 額度。
"""

import json
from collections.abc import Callable, Collection
from pathlib import Path

from buddy_host.narration.preparer import PreparedNarration, wav_seconds
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
        **_: object,  # 旅程記憶（recent_topics、told_before）：重播的是現成的稿子，用不到
    ) -> list[PreparedNarration]:
        found: list[tuple[float, PreparedNarration]] = []
        for meta_path in sorted(self._directory.glob("*.meta.json")):
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            wav = _find_wav(meta_path)
            if meta["candidate_id"] in exclude_ids or wav is None:
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
                        meta.get("audio_seconds") or wav_seconds(wav),
                        round(distance, 1),
                        meta["lat"],
                        meta["lon"],
                    ),
                )
            )
        found.sort(key=lambda pair: pair[0])
        return [item for _, item in found[: self._limit]]


def _find_wav(meta_path: Path) -> Path | None:
    name = meta_path.name.removesuffix(".meta.json") + ".wav"
    flat = meta_path.with_name(name)
    if flat.exists():
        return flat
    return next(iter(sorted(meta_path.parent.glob(f"*/{name}"))), None)
