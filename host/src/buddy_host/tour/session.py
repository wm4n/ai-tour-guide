"""一趟旅程的主機端狀態：App 回報位置，這裡決定何時為哪裡準備介紹，並把做好的通知出去。

準備很慢（寫稿＋合成＋驗收，一段可能數分鐘）而且只有一顆 GPU，所以：
- 同一時間只跑一次準備；
- 準備期間進來的位置只保留最新一筆，跑完再看要不要接著準備。
"""

import asyncio
import logging
import time
from collections.abc import Callable, Collection
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
DEFAULT_RETRY_AFTER_FAILURE_S = 60.0
DEFAULT_QUOTA_RETRY_AFTER_S = 900.0  # 不知道額度何時恢復時，隔這麼久再試一次


class TourNotActiveError(RuntimeError):
    pass


class PreparerLike(Protocol):
    async def prepare(
        self,
        location: Location,
        *,
        exclude_ids: Collection[str] = (),
        traveler: TravelerContext | None = None,
        on_ready: Callable[[PreparedNarration], None] | None = None,
    ) -> list[PreparedNarration]: ...


@dataclass(frozen=True)
class TourFix:
    """App 一次回報的內容：位置、行進方向，以及當下的旅人狀態。"""

    location: Location
    traveler: TravelerContext


@dataclass(frozen=True)
class TourRecap:
    """一趟結束時留下的紀錄，用量報告用（時間都是 epoch 秒）。"""

    started_at: float
    ended_at: float
    narrations: int
    stopped_reason: str | None


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
        self,
        preparer: PreparerLike,
        *,
        reprepare_distance_m: float = DEFAULT_REPREPARE_DISTANCE_M,
        retry_after_failure_s: float = DEFAULT_RETRY_AFTER_FAILURE_S,
        quota_retry_after_s: float = DEFAULT_QUOTA_RETRY_AFTER_S,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,  # 額度恢復時間（resetsAt）是牆鐘時間
    ):
        self._preparer = preparer
        self._reprepare_distance_m = reprepare_distance_m
        self._retry_after_failure_s = retry_after_failure_s
        self._quota_retry_after_s = quota_retry_after_s
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._started_at: float | None = None
        self._quota_resumes_at: float | None = None  # 額度停止中：何時可以再試
        self._failed_at: float | None = None  # 最近一次準備失敗的時間；冷卻後即使沒移動也重試
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
        self._started_at = self._wall_clock()
        self._schedule(fix)

    def report(self, fix: TourFix) -> None:
        if not self.active:
            raise TourNotActiveError("還沒有出發")
        if self._quota_may_have_recovered():
            self._resume_after_quota(fix)
        elif self.stopped_reason is None and self._needs_preparation(fix):
            self._schedule(fix)

    def end(self) -> TourRecap | None:
        """結束這一趟；沒有進行中的旅程時回傳 None。"""
        recap = None
        if self.active and self._started_at is not None:
            recap = TourRecap(
                self._started_at, self._wall_clock(), len(self._events), self.stopped_reason
            )
        self._reset()
        return recap

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
        self._started_at = None
        self._quota_resumes_at = None
        self._failed_at = None
        self._events = []
        self._audio = {}
        self.active = False
        self.stopped_reason = None

    def _quota_may_have_recovered(self) -> bool:
        return (
            self.stopped_reason == "quota"
            and self._quota_resumes_at is not None
            and self._wall_clock() >= self._quota_resumes_at
        )

    def _resume_after_quota(self, fix: TourFix) -> None:
        """不另外探測額度：直接再準備一次，這次呼叫就是探測；還是被拒絕會再停下。"""
        self.stopped_reason = None
        self._quota_resumes_at = None
        self._schedule(fix)  # 繞過 _needs_preparation：人可能沒走多遠，但該準備的還沒準備

    def _needs_preparation(self, fix: TourFix) -> bool:
        anchor = self._anchor
        if anchor is None:
            return True
        if (
            self._failed_at is not None
            and self._monotonic() - self._failed_at >= self._retry_after_failure_s
        ):
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
                    fix.location,
                    exclude_ids=set(self._audio),
                    traveler=fix.traveler,
                    # 準備一段要數分鐘：做好一段就通知一段，不等整批
                    on_ready=lambda item: self._publish_if_current(generation, item),
                )
            except LlmBudgetExhaustedError:
                self._stop(generation, "llm_budget")
                return
            except QuotaExceededError as error:
                self._stop(generation, "quota", error.resets_at)
                return
            except ForbiddenModelError:
                self._stop(generation, "forbidden_model")
                return
            except Exception:  # 一次準備失敗（網路、逾時…）不結束整趟，等下次移動再試
                logger.exception("為 %s 準備介紹失敗", fix.location)
                self._failed_at = self._monotonic()
                continue
            if generation != self._generation:
                return
            self._failed_at = None
            for item in prepared:
                self._publish_if_current(generation, item)

    def _stop(self, generation: int, reason: str, resets_at: float | None = None) -> None:
        if generation != self._generation:
            return
        self.stopped_reason = reason
        self._pending = None
        if reason == "quota":
            now = self._wall_clock()
            # 沒給或已過期的恢復時間不可信：否則每次回報位置都會重試一次
            known = resets_at is not None and resets_at > now
            self._quota_resumes_at = resets_at if known else now + self._quota_retry_after_s
        logger.warning("停止準備介紹：%s", reason)

    def _publish_if_current(self, generation: int, item: PreparedNarration) -> None:
        if generation == self._generation and item.candidate_id not in self._audio:
            self._publish(item)

    def _publish(self, item: PreparedNarration) -> None:
        self._seq += 1
        self._audio[item.candidate_id] = item.wav_path
        self._events.append(
            NarrationEvent(
                self._seq, item.candidate_id, item.name, item.lat, item.lon, item.audio_seconds
            )
        )
