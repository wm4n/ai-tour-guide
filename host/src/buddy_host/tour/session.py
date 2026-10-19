"""一趟旅程的主機端狀態：App 回報位置，這裡決定何時為哪裡準備介紹，並把做好的通知出去。

準備很慢（寫稿＋合成＋驗收，一段可能數分鐘）而且只有一顆 GPU，所以：
- 同一時間只跑一次準備；
- 準備期間進來的位置只保留最新一筆，跑完再看要不要接著準備。
"""

import asyncio
import logging
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import ForbiddenModelError
from buddy_host.narration.preparer import PreparedNarration
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.geo import haversine_m
from buddy_host.places.models import Location

logger = logging.getLogger(__name__)

DEFAULT_REPREPARE_DISTANCE_M = 250.0


class TourNotActiveError(RuntimeError):
    pass


class PreparerLike(Protocol):
    async def prepare(
        self,
        location: Location,
        *,
        exclude_ids: Collection[str] = (),
        traveler: TravelerContext | None = None,
    ) -> list[PreparedNarration]: ...


@dataclass(frozen=True)
class TourFix:
    """App 一次回報的內容：位置、行進方向，以及當下的旅人狀態。"""

    location: Location
    traveler: TravelerContext


@dataclass(frozen=True)
class NarrationEvent:
    seq: int
    id: str
    name: str
    lat: float
    lon: float
    audio_seconds: float


class TourSession:
    def __init__(
        self, preparer: PreparerLike, *, reprepare_distance_m: float = DEFAULT_REPREPARE_DISTANCE_M
    ):
        self._preparer = preparer
        self._reprepare_distance_m = reprepare_distance_m
        self._seq = 0  # 跨趟持續遞增，App 的游標才不會在新的一趟失效
        self._generation = 0
        self._worker: asyncio.Task | None = None
        self._pending: TourFix | None = None
        self._anchor: TourFix | None = None  # 最近一次排進準備的回報，之後的移動以它為準
        self._events: list[NarrationEvent] = []
        self._audio: dict[str, Path] = {}
        self.active = False
        self.stopped_reason: str | None = None

    @property
    def preparing(self) -> bool:
        return self._worker is not None and not self._worker.done()

    def start(self, fix: TourFix) -> None:
        self._reset()
        self.active = True
        self._schedule(fix)

    def report(self, fix: TourFix) -> None:
        if not self.active:
            raise TourNotActiveError("還沒有出發")
        if self.stopped_reason is None and self._needs_preparation(fix):
            self._schedule(fix)

    def end(self) -> None:
        self._reset()

    def narrations_after(self, seq: int) -> list[NarrationEvent]:
        return [event for event in self._events if event.seq > seq]

    def audio_path(self, narration_id: str) -> Path | None:
        return self._audio.get(narration_id)

    async def wait_idle(self) -> None:
        while self._worker is not None and not self._worker.done():
            await asyncio.wait([self._worker])

    def _reset(self) -> None:
        self._generation += 1
        if self._worker is not None:
            self._worker.cancel()
        self._worker = None
        self._pending = None
        self._anchor = None
        self._events = []
        self._audio = {}
        self.active = False
        self.stopped_reason = None

    def _needs_preparation(self, fix: TourFix) -> bool:
        anchor = self._anchor
        if anchor is None:
            return True
        if fix.traveler.key() != anchor.traveler.key():
            return True
        moved = haversine_m(
            anchor.location.lat, anchor.location.lon, fix.location.lat, fix.location.lon
        )
        return moved >= self._reprepare_distance_m

    def _schedule(self, fix: TourFix) -> None:
        self._pending = fix
        self._anchor = fix
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(self._generation))

    async def _run(self, generation: int) -> None:
        while self._pending is not None and generation == self._generation:
            fix, self._pending = self._pending, None
            try:
                prepared = await self._preparer.prepare(
                    fix.location, exclude_ids=set(self._audio), traveler=fix.traveler
                )
            except QuotaExceededError as error:
                reason = "llm_budget" if isinstance(error, LlmBudgetExhaustedError) else "quota"
                self._stop(generation, reason)
                return
            except ForbiddenModelError:
                self._stop(generation, "forbidden_model")
                return
            except Exception:  # 一次準備失敗（網路、逾時…）不結束整趟，等下次移動再試
                logger.exception("為 %s 準備介紹失敗", fix.location)
                continue
            if generation != self._generation:
                return
            for item in prepared:
                self._publish(item)

    def _stop(self, generation: int, reason: str) -> None:
        if generation != self._generation:
            return
        self.stopped_reason = reason
        self._pending = None
        logger.warning("停止準備介紹：%s", reason)

    def _publish(self, item: PreparedNarration) -> None:
        self._seq += 1
        self._audio[item.candidate_id] = item.wav_path
        self._events.append(
            NarrationEvent(
                self._seq, item.candidate_id, item.name, item.lat, item.lon, item.audio_seconds
            )
        )
