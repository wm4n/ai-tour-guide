"""一趟旅程的主機端狀態：App 回報位置，這裡決定何時為哪裡準備介紹，並把做好的通知出去。

準備很慢（寫稿＋合成＋驗收，一段可能數分鐘）而且只有一顆 GPU，所以：
- 同一時間只跑一次準備；
- 準備期間進來的位置只保留最新一筆，跑完再看要不要接著準備。

換聲音時，已發布但 App 還沒播完的介紹撤下，把同一份稿子用新聲音重新合成後再發布（先於下一次
準備）。不是在最後的位置重新準備：「這趟剛講過什麼」變了，快取的指紋就對不上，會重寫稿。
"""

import asyncio
import logging
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import ForbiddenModelError
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.preparer import PreparedNarration
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.geo import haversine_m
from buddy_host.places.models import Location
from buddy_host.speech.units import unit_starts
from buddy_host.tour.journey import JourneyMemory

logger = logging.getLogger(__name__)

DEFAULT_REPREPARE_DISTANCE_M = 250.0
DEFAULT_RETRY_AFTER_FAILURE_S = 60.0
DEFAULT_QUOTA_RETRY_AFTER_S = 900.0  # 不知道額度何時恢復時，隔這麼久再試一次（沒傳入共用閘門時）


class TourNotActiveError(RuntimeError):
    pass


class PreparerLike(Protocol):
    voice_key: str  # 之後做的介紹用的聲音；換聲音時由旅程改

    async def prepare(
        self,
        location: Location,
        *,
        exclude_ids: Collection[str] = (),
        traveler: TravelerContext | None = None,
        recent_topics: tuple[str, ...] = (),
        told_before: Mapping[str, tuple[str, ...]] | None = None,
        on_ready: Callable[[PreparedNarration], None] | None = None,
    ) -> list[PreparedNarration]: ...

    async def revoice(
        self,
        narrations: Collection[PreparedNarration],
        *,
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
class StartOutcome:
    resumed: bool  # 接續了上一趟（重開 App 時距離上次活動不到 2 小時）
    abandoned: TourRecap | None  # 上一趟沒按結束就被丟下了：呼叫端替它寫用量報告


@dataclass(frozen=True)
class NarrationEvent:
    seq: int
    id: str
    name: str
    lat: float
    lon: float
    audio_seconds: float
    voice: str  # 聲音鍵：App 只收目前聲音的介紹
    # 各個合成單位（句）開始播放的秒數：被問題打斷時，App 回到被打斷那一句的開頭
    unit_starts: tuple[float, ...] = ()


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
        journey: JourneyMemory | None = None,
        quota: QuotaGate | None = None,  # 與問答共用：任一邊撞到額度，兩邊一起停
    ):
        self._preparer = preparer
        self._reprepare_distance_m = reprepare_distance_m
        self._retry_after_failure_s = retry_after_failure_s
        self._quota = quota or QuotaGate(retry_after_s=quota_retry_after_s, wall_clock=wall_clock)
        self._monotonic = monotonic
        self._wall_clock = wall_clock
        self._journey = journey if journey is not None else JourneyMemory(None)
        self._started_at: float | None = None
        self._failed_at: float | None = None  # 最近一次準備失敗的時間；冷卻後即使沒移動也重試
        self._seq = 0  # 跨趟持續遞增，App 的游標才不會在新的一趟失效
        self._generation = 0
        self._worker: asyncio.Task | None = None
        self._pending: TourFix | None = None
        self._anchor: TourFix | None = None  # 最近一次排進準備的回報，之後的移動以它為準
        self._events: list[NarrationEvent] = []
        self._audio: dict[str, Path] = {}
        self._published: dict[str, PreparedNarration] = {}
        self._played: set[str] = set()  # App 回報播完的
        self._redo: dict[str, PreparedNarration] = {}  # 換聲音撤下、等著用新聲音重做的
        # 換聲音撤下過的地方：這趟不再重新準備（指紋對不上會重寫稿），重做失敗也一樣
        self._withdrawn: set[str] = set()
        self.active = False
        self._stopped_reason: str | None = None  # 額度以外的停止原因；額度看共用閘門

    @property
    def stopped_reason(self) -> str | None:
        if self.active and self._quota.tripped:
            return "quota"
        return self._stopped_reason

    @property
    def voice_key(self) -> str:
        return self._preparer.voice_key

    @property
    def preparing(self) -> bool:
        return self._worker is not None and not self._worker.done()

    def start(self, fix: TourFix) -> StartOutcome:
        self._reset()
        now = self._wall_clock()
        began = self._journey.begin(now)
        self.active = True
        self._started_at = self._journey.trip_started_at  # 接續時，報告要涵蓋整趟
        self._schedule(fix)
        abandoned = began.abandoned
        return StartOutcome(
            began.resumed,
            TourRecap(
                started_at=abandoned.started_at,
                ended_at=abandoned.last_activity_at,
                narrations=len(abandoned.stops),
                stopped_reason=None,
            )
            if abandoned
            else None,
        )

    def report(self, fix: TourFix) -> None:
        if not self.active:
            raise TourNotActiveError("還沒有出發")
        self._journey.touch(self._wall_clock())
        if self._quota.may_probe():
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
        if self.active:
            self._journey.finish(self._wall_clock())
        self._reset()
        return recap

    def mark_played(self, narration_id: str) -> bool:
        """App 回報這段播完了：這時才算「講過」，記進旅程記憶。重送不會重複記。"""
        item = self._published.get(narration_id)
        if item is None:
            return False
        self._played.add(narration_id)
        self._journey.record_told(self._wall_clock(), item.candidate_id, item.name, item.script)
        return True

    def change_voice(self, voice_key: str, *, playing_id: str | None = None) -> None:
        """之後的介紹改用這個聲音；連續切換以最後一次為準。

        旅程中：已發布但 App 還沒回報播完的介紹撤下（`playing_id` 是正在播、會播完的那段，留著），
        用新聲音重新合成同一份稿子後再發布，不呼叫 Claude。進行中的準備不中斷：寫好的稿子
        直接用新聲音合成。
        """
        if voice_key == self.voice_key:
            return
        self._preparer.voice_key = voice_key
        if not self.active:
            return
        withdrawn = {
            narration_id: item
            for narration_id, item in self._published.items()
            if narration_id not in self._played and narration_id != playing_id
        }
        for narration_id in withdrawn:
            del self._published[narration_id]
            del self._audio[narration_id]
        self._events = [event for event in self._events if event.id not in withdrawn]
        self._withdrawn |= withdrawn.keys()
        self._redo.update(withdrawn)
        self._ensure_worker()

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
        self._failed_at = None
        self._events = []
        self._audio = {}
        self._published = {}
        self._played = set()
        self._redo = {}
        self._withdrawn = set()
        self.active = False
        self._stopped_reason = None

    def _resume_after_quota(self, fix: TourFix) -> None:
        """不另外探測額度：直接再準備一次，這次呼叫就是探測（閘門在 `_run` 裡打開）。"""
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
        self._ensure_worker()

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(self._generation))

    async def _run(self, generation: int) -> None:
        while (self._redo or self._pending is not None) and generation == self._generation:
            if self._redo:  # 重做不呼叫 Claude：不看額度，先於下一次準備
                await self._revoice(generation)
                continue
            if not self._quota.admit():  # 問答先撞到額度了：不再呼叫 Claude，等恢復
                self._pending = None
                # 這次沒準備成：忘掉錨點，之後不論誰先把閘門打開，下一次回報都會補做，
                # 不必等人走滿重新準備的距離
                self._anchor = None
                return
            fix, self._pending = self._pending, None
            try:
                prepared = await self._preparer.prepare(
                    fix.location,
                    exclude_ids=set(self._audio) | self._withdrawn | self._journey.stop_ids(),
                    traveler=fix.traveler,
                    recent_topics=self._journey.recent_topics(),
                    told_before=self._journey.told_before(),
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

    async def _revoice(self, generation: int) -> None:
        items, self._redo = list(self._redo.values()), {}
        try:
            redone = await self._preparer.revoice(
                items, on_ready=lambda item: self._publish_if_current(generation, item)
            )
        except Exception:
            logger.exception("用新聲音重做介紹失敗")
            return
        for item in redone:
            self._publish_if_current(generation, item)

    def _stop(self, generation: int, reason: str, resets_at: float | None = None) -> None:
        if generation != self._generation:
            return
        self._pending = None
        if reason == "quota":
            self._quota.trip(resets_at)
            # 這次沒準備成：忘掉錨點。額度恢復後若是問答先探測成功、把閘門打開，
            # 下一次回報才會補準備，不必等人走滿重新準備的距離
            self._anchor = None
        else:
            self._stopped_reason = reason
        logger.warning("停止準備介紹：%s", reason)

    def _publish_if_current(self, generation: int, item: PreparedNarration) -> None:
        # 聲音不對的是換聲音之前做好、已經撤下等重做的（例如準備做完時整批回傳的那幾段）
        if (
            generation == self._generation
            and item.voice == self.voice_key
            and item.candidate_id not in self._audio
        ):
            self._publish(item)

    def _publish(self, item: PreparedNarration) -> None:
        self._seq += 1
        self._audio[item.candidate_id] = item.wav_path
        self._published[item.candidate_id] = item
        self._events.append(
            NarrationEvent(
                self._seq,
                item.candidate_id,
                item.name,
                item.lat,
                item.lon,
                item.audio_seconds,
                item.voice,
                unit_starts(item.wav_path),  # 從 wav 偵測：快取命中的舊介紹也有
            )
        )
