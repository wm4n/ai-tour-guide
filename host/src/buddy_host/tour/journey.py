"""旅程記憶（設計文件第 7 節）：這趟去過哪裡、講過什麼，以及跨趟永久記得講過的景點。

- 「講過」以 App 回報播完為準：主機準備好但被 App 丟掉的不算，使用者沒聽過就不該記。
- 一趟從按「出發」到按「結束」；中途被關掉（沒按結束）的，隔不到 2 小時再出發就接續同一趟。
- 檔案放在 `~/.buddy-host/`（是位置歷史，不入 repo）；寫入用暫存檔再 replace，壞檔改名留存。
  `path=None` 只存在記憶體裡（桌上重播模式不該寫進真實的永久記錄）。
- 給 Claude 的摘要有上限：這趟最近幾個地方的名字，以及每個地方最近幾次講過的稿子（截斷）。
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

RESUME_WINDOW_S = 2 * 3600.0
ACTIVITY_SAVE_INTERVAL_S = 60.0  # 位置回報很頻繁，最後活動時間不必每次都寫檔
KEPT_TELLINGS = 5  # 檔案裡每個地方最多留幾次講過的稿子


@dataclass(frozen=True)
class Stop:
    id: str
    name: str
    at: float


@dataclass
class Trip:
    started_at: float
    last_activity_at: float
    ended: bool = False
    stops: list[Stop] = field(default_factory=list)


@dataclass(frozen=True)
class BeginResult:
    resumed: bool
    abandoned: Trip | None  # 上一趟沒按結束、又超過 2 小時：呼叫端要替它收尾（寫用量報告）


class JourneyMemory:
    def __init__(
        self,
        path: Path | None = None,
        *,
        resume_window_s: float = RESUME_WINDOW_S,
        max_recent: int = 5,
        told_per_place: int = 2,
        told_chars: int = 300,
    ):
        self._path = path
        self._resume_window_s = resume_window_s
        self._max_recent = max_recent
        self._told_per_place = told_per_place
        self._told_chars = told_chars
        self._visited: dict[str, dict] = {}  # id → {"name": str, "told": [{"at", "script"}]}
        self._trip: Trip | None = None
        self._saved_at = 0.0
        self._load()

    @property
    def trip_started_at(self) -> float | None:
        return self._trip.started_at if self._trip else None

    def begin(self, now: float) -> BeginResult:
        trip = self._trip
        open_trip = trip if trip and not trip.ended else None
        if open_trip and now - open_trip.last_activity_at < self._resume_window_s:
            open_trip.last_activity_at = now
            self._save(now)
            return BeginResult(resumed=True, abandoned=None)
        self._trip = Trip(started_at=now, last_activity_at=now)
        self._save(now)
        return BeginResult(resumed=False, abandoned=open_trip)

    def touch(self, now: float) -> None:
        if self._trip and not self._trip.ended:
            self._trip.last_activity_at = now
            if now - self._saved_at >= ACTIVITY_SAVE_INTERVAL_S:
                self._save(now)

    def finish(self, now: float) -> None:
        if self._trip:
            self._trip.ended = True
            self._trip.last_activity_at = now
            self._save(now)

    def record_told(self, now: float, candidate_id: str, name: str, script: str) -> None:
        trip = self._trip
        if trip is None or trip.ended or candidate_id in self.stop_ids():
            return
        trip.stops.append(Stop(candidate_id, name, now))
        trip.last_activity_at = now
        place = self._visited.setdefault(candidate_id, {"name": name, "told": []})
        place["name"] = name
        place["told"] = [*place["told"], {"at": now, "script": script}][-KEPT_TELLINGS:]
        self._save(now)

    def stop_ids(self) -> set[str]:
        return {stop.id for stop in self._trip.stops} if self._trip else set()

    def recent_topics(self) -> tuple[str, ...]:
        """這趟最近講過的地方（舊的在前）。"""
        stops = self._trip.stops if self._trip else []
        return tuple(stop.name for stop in stops[-self._max_recent :])

    def last_told(self) -> tuple[str, str] | None:
        """這趟最近一段播完的介紹（地方名、截斷的稿子）。「再多說一點」要接著它講。"""
        stops = self._trip.stops if self._trip else []
        if not stops:
            return None
        told = self._visited.get(stops[-1].id, {}).get("told")
        return (stops[-1].name, self._clip(told[-1]["script"])) if told else None

    def told_before(self) -> dict[str, tuple[str, ...]]:
        """每個講過的地方最近幾次的稿子（各自截斷），讓 Claude 換個角度講。"""
        return {
            place_id: tuple(
                self._clip(telling["script"]) for telling in place["told"][-self._told_per_place :]
            )
            for place_id, place in self._visited.items()
            if place["told"]
        }

    def _clip(self, text: str) -> str:
        text = text.strip()
        if len(text) <= self._told_chars:
            return text
        return text[: self._told_chars - 1] + "…"

    def _load(self) -> None:
        if self._path is None or not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._visited = {
                place_id: {
                    "name": place["name"],
                    "told": [
                        {"at": float(t["at"]), "script": str(t["script"])} for t in place["told"]
                    ],
                }
                for place_id, place in data["visited"].items()
            }
            trip = data["trip"]
            self._trip = (
                Trip(
                    float(trip["started_at"]),
                    float(trip["last_activity_at"]),
                    bool(trip["ended"]),
                    [Stop(s["id"], s["name"], float(s["at"])) for s in trip["stops"]],
                )
                if trip
                else None
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            kept = self._path.with_name(f"{self._path.name}.corrupt-{int(time.time())}")
            logger.exception("旅程記憶檔壞了，改名留存為 %s，從空的開始", kept)
            self._visited, self._trip = {}, None
            try:
                self._path.replace(kept)
            except OSError:
                logger.exception("壞掉的旅程記憶檔連改名都失敗")

    def _save(self, now: float) -> None:
        self._saved_at = now
        if self._path is None:
            return
        try:
            self._write()
        except OSError:
            # 寫不進去不該讓旅程停擺：記憶體裡照常運作，只是重啟後會忘記
            logger.exception("旅程記憶存檔失敗：%s", self._path)

    def _write(self) -> None:
        assert self._path is not None
        data = {
            "visited": self._visited,
            "trip": None
            if self._trip is None
            else {
                "started_at": self._trip.started_at,
                "last_activity_at": self._trip.last_activity_at,
                "ended": self._trip.ended,
                "stops": [{"id": s.id, "name": s.name, "at": s.at} for s in self._trip.stops],
            },
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_name(self._path.name + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temp, self._path)
