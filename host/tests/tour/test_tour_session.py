import asyncio
import dataclasses
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.preparer import PreparedNarration
from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode
from buddy_host.places.models import Location
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix, TourNotActiveError, TourSession

TAIPEI = timezone(timedelta(hours=8))
START = Location(25.0560, 121.5100, heading_deg=200.0)
M_PER_DEG_LAT = 111_195


def north_of(base: Location, meters: float) -> Location:
    return Location(base.lat + meters / M_PER_DEG_LAT, base.lon, base.heading_deg)


def fix(location=START, **traveler) -> TourFix:
    context = TravelerContext(
        mode=traveler.pop("mode", TravelMode.WALKING),
        companions=traveler.pop("companions", Companions.SOLO),
        local_time=datetime(2026, 10, 20, 15, 0, tzinfo=TAIPEI),
        **traveler,
    )
    return TourFix(location, context)


def narration(name: str, tmp_path: Path, voice: str = "F2@1.2") -> PreparedNarration:
    wav = tmp_path / f"{name}.wav"
    wav.write_bytes(b"RIFF")
    return PreparedNarration(
        f"wiki:{name}", name, f"{name}的稿子", wav, tmp_path / f"{name}.json", 31.5, 80.0,
        25.05, 121.51, voice,
    )  # fmt: skip


class FakePreparer:
    """每次 prepare 依序回傳預先排好的結果；gate 讓測試卡住一次準備。

    結果裡的名稱做成目前聲音的介紹；`revoice` 把稿子換成目前的聲音（記下被重做的）。
    """

    def __init__(self, tmp_path: Path, results=None):
        self.tmp_path = tmp_path
        self.results = list(results or [])
        self.voice_key = "F2@1.2"
        self.revoiced: list[list[str]] = []
        self.revoice_gate: asyncio.Event | None = None
        self.revoice_error: Exception | None = None
        self.calls: list[dict] = []
        self.gate: asyncio.Event | None = None
        self.running = 0
        self.max_running = 0
        self.report_progressively = False
        self.gate_after_first: asyncio.Event | None = None

    async def prepare(
        self,
        location,
        *,
        exclude_ids=(),
        traveler=None,
        on_ready=None,
        recent_topics=(),
        told_before=None,
        **_,
    ):
        self.calls.append(
            {
                "location": location,
                "exclude_ids": set(exclude_ids),
                "traveler": traveler,
                "recent_topics": tuple(recent_topics),
                "told_before": dict(told_before or {}),
            }
        )
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            if self.gate:
                await self.gate.wait()
            result = self.results.pop(0) if self.results else []
            if isinstance(result, Exception):
                raise result

            def made(n):  # 和真的準備器一樣：每段都是做好當下的聲音
                return narration(n, self.tmp_path, self.voice_key) if isinstance(n, str) else n

            if on_ready and self.report_progressively:
                items = []
                for n in result:
                    items.append(made(n))
                    on_ready(items[-1])
                    if self.gate_after_first:
                        await self.gate_after_first.wait()
                return items
            return [made(n) for n in result]
        finally:
            self.running -= 1

    async def revoice(self, narrations, *, on_ready=None):
        self.revoiced.append([item.candidate_id for item in narrations])
        if self.revoice_gate:
            await self.revoice_gate.wait()
        if self.revoice_error:
            raise self.revoice_error
        redone = [dataclasses.replace(item, voice=self.voice_key) for item in narrations]
        for item in redone:
            if on_ready:
                on_ready(item)
        return redone


async def test_start_prepares_the_area_around_the_start_point_with_the_traveler_state(tmp_path):
    preparer = FakePreparer(tmp_path, [["A", "B"]])
    session = TourSession(preparer)

    session.start(fix(with_children=True))
    await session.wait_idle()

    call = preparer.calls[0]
    assert call["location"] == START
    assert call["traveler"].with_children is True
    assert [e.name for e in session.narrations_after(0)] == ["A", "B"]


async def test_each_narration_is_published_as_soon_as_it_is_ready(tmp_path):
    preparer = FakePreparer(tmp_path, [["A", "B"]])
    preparer.report_progressively = True
    preparer.gate_after_first = asyncio.Event()
    session = TourSession(preparer)

    session.start(fix())
    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert [e.name for e in session.narrations_after(0)] == ["A"]  # B 還在準備，A 已可取用
    preparer.gate_after_first.set()
    await session.wait_idle()
    assert [e.name for e in session.narrations_after(0)] == ["A", "B"]  # 不會重複發佈 A


async def test_events_carry_position_length_and_a_growing_sequence(tmp_path):
    session = TourSession(FakePreparer(tmp_path, [["A", "B"]]))

    session.start(fix())
    await session.wait_idle()

    first, second = session.narrations_after(0)
    assert (first.seq, second.seq) == (1, 2)
    assert (first.id, first.lat, first.lon, first.audio_seconds) == ("wiki:A", 25.05, 121.51, 31.5)
    assert [e.name for e in session.narrations_after(1)] == ["B"]
    assert session.narrations_after(2) == []


async def test_small_moves_do_not_prepare_again_but_a_long_move_does(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"], ["B"]])
    session = TourSession(preparer, reprepare_distance_m=250)
    session.start(fix())
    await session.wait_idle()

    session.report(fix(north_of(START, 100)))
    await session.wait_idle()
    assert len(preparer.calls) == 1

    session.report(fix(north_of(START, 300)))
    await session.wait_idle()
    assert len(preparer.calls) == 2
    assert preparer.calls[1]["exclude_ids"] == {"wiki:A"}
    assert [e.name for e in session.narrations_after(0)] == ["A", "B"]


async def test_only_one_preparation_runs_and_the_latest_position_wins(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"], ["B"]])
    preparer.gate = asyncio.Event()
    session = TourSession(preparer, reprepare_distance_m=250)
    session.start(fix())
    await asyncio.sleep(0)

    for meters in (300, 600, 900):
        session.report(fix(north_of(START, meters)))
    preparer.gate.set()
    await session.wait_idle()

    assert preparer.max_running == 1
    assert [c["location"] for c in preparer.calls] == [START, north_of(START, 900)]


async def test_positions_during_a_run_are_compared_with_the_run_in_progress(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"]])
    preparer.gate = asyncio.Event()
    session = TourSession(preparer, reprepare_distance_m=250)
    session.start(fix())
    await asyncio.sleep(0)

    session.report(fix(north_of(START, 100)))  # 還在準備起點附近，不必再排一次
    preparer.gate.set()
    await session.wait_idle()

    assert len(preparer.calls) == 1


async def test_a_changed_traveler_state_prepares_again_even_without_moving(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"], ["B"]])
    session = TourSession(preparer)
    session.start(fix(companions=Companions.SOLO))
    await session.wait_idle()

    session.report(fix(companions=Companions.FAMILY))
    await session.wait_idle()

    assert len(preparer.calls) == 2
    assert preparer.calls[1]["traveler"].companions == Companions.FAMILY


async def test_the_same_traveler_state_at_the_same_place_does_not_prepare_again(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"]])
    session = TourSession(preparer)
    session.start(fix())
    await session.wait_idle()

    session.report(fix())
    await session.wait_idle()

    assert len(preparer.calls) == 1


async def test_quota_or_budget_exhaustion_stops_preparing_and_says_why(tmp_path):
    for error, reason in (
        (QuotaExceededError("limit"), "quota"),
        (LlmBudgetExhaustedError("budget"), "llm_budget"),
    ):
        preparer = FakePreparer(tmp_path, [["A"], error, ["C"]])
        session = TourSession(preparer, reprepare_distance_m=100)
        session.start(fix())
        await session.wait_idle()

        session.report(fix(north_of(START, 200)))
        await session.wait_idle()
        session.report(fix(north_of(START, 500)))
        await session.wait_idle()

        assert session.stopped_reason == reason
        assert len(preparer.calls) == 2  # 停下之後不再嘗試
        assert [e.name for e in session.narrations_after(0)] == ["A"]


async def test_one_failed_preparation_does_not_end_the_tour(tmp_path):
    preparer = FakePreparer(tmp_path, [RuntimeError("overpass down"), ["B"]])
    session = TourSession(preparer, reprepare_distance_m=100)
    session.start(fix())
    await session.wait_idle()

    session.report(fix(north_of(START, 200)))
    await session.wait_idle()

    assert session.stopped_reason is None
    assert [e.name for e in session.narrations_after(0)] == ["B"]


async def test_a_failed_preparation_is_retried_after_a_cooldown_even_without_moving(tmp_path):
    clock = {"now": 1000.0}
    preparer = FakePreparer(tmp_path, [RuntimeError("overpass down"), ["A"]])
    session = TourSession(preparer, retry_after_failure_s=60, monotonic=lambda: clock["now"])
    session.start(fix())
    await session.wait_idle()

    clock["now"] += 30
    session.report(fix())  # 冷卻中：不重試，免得對掛掉的服務狂打
    await session.wait_idle()
    assert len(preparer.calls) == 1

    clock["now"] += 31
    session.report(fix())
    await session.wait_idle()
    assert [e.name for e in session.narrations_after(0)] == ["A"]


async def test_reporting_without_a_tour_is_an_error(tmp_path):
    session = TourSession(FakePreparer(tmp_path))

    with pytest.raises(TourNotActiveError):
        session.report(fix())


async def test_end_cancels_the_running_preparation(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"]])
    preparer.gate = asyncio.Event()
    session = TourSession(preparer)
    session.start(fix())
    await asyncio.sleep(0)

    session.end()
    await session.wait_idle()

    assert session.active is False
    assert session.preparing is False
    assert session.narrations_after(0) == []
    with pytest.raises(TourNotActiveError):
        session.report(fix())


async def test_starting_again_begins_a_fresh_tour_but_keeps_sequence_numbers_growing(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"], ["B"]])
    session = TourSession(preparer)
    session.start(fix())
    await session.wait_idle()

    session.start(fix())
    await session.wait_idle()

    events = session.narrations_after(0)
    assert [(e.seq, e.name) for e in events] == [(2, "B")]
    assert preparer.calls[1]["exclude_ids"] == set()


async def test_audio_is_only_served_for_narrations_of_this_tour(tmp_path):
    session = TourSession(FakePreparer(tmp_path, [["A"]]))
    session.start(fix())
    await session.wait_idle()

    assert session.audio_path("wiki:A") == tmp_path / "A.wav"
    assert session.audio_path("../../etc/passwd") is None
    assert session.audio_path("wiki:nope") is None


class WallClock:
    def __init__(self, now=1_000_000.0):
        self.now = now

    def __call__(self):
        return self.now


async def test_a_quota_stop_ends_by_itself_once_the_limit_resets(tmp_path):
    clock = WallClock()
    preparer = FakePreparer(
        tmp_path, [QuotaExceededError("limit", resets_at=clock.now + 3600), ["A"]]
    )
    session = TourSession(preparer, wall_clock=clock)
    session.start(fix())
    await session.wait_idle()
    assert session.stopped_reason == "quota"

    clock.now += 3599
    session.report(fix())
    await session.wait_idle()
    assert session.stopped_reason == "quota"  # 還沒到
    assert len(preparer.calls) == 1

    clock.now += 2
    session.report(fix())
    await session.wait_idle()

    assert session.stopped_reason is None
    assert [e.name for e in session.narrations_after(0)] == ["A"]


async def test_recovery_prepares_around_the_latest_position_even_if_barely_moved(tmp_path):
    clock = WallClock()
    preparer = FakePreparer(
        tmp_path, [QuotaExceededError("limit", resets_at=clock.now + 60), ["A"]]
    )
    session = TourSession(preparer, wall_clock=clock)
    session.start(fix())
    await session.wait_idle()

    near = north_of(START, 40)  # 離準備失敗的那一點不到重新準備的距離
    session.report(fix(near))
    clock.now += 61
    session.report(fix(near))
    await session.wait_idle()

    assert preparer.calls[1]["location"] == near


async def test_without_a_reset_time_the_preparation_is_retried_after_a_cooldown(tmp_path):
    clock = WallClock()
    preparer = FakePreparer(tmp_path, [QuotaExceededError("limit"), ["A"]])
    session = TourSession(preparer, wall_clock=clock, quota_retry_after_s=900)
    session.start(fix())
    await session.wait_idle()

    clock.now += 899
    session.report(fix())
    await session.wait_idle()
    assert len(preparer.calls) == 1

    clock.now += 2
    session.report(fix())
    await session.wait_idle()

    assert session.stopped_reason is None
    assert len(preparer.calls) == 2


async def test_a_limit_that_is_still_hit_stops_again_with_the_new_reset_time(tmp_path):
    clock = WallClock()
    preparer = FakePreparer(
        tmp_path,
        [
            QuotaExceededError("limit", resets_at=clock.now + 60),
            QuotaExceededError("limit", resets_at=clock.now + 7200),
            ["A"],
        ],
    )
    session = TourSession(preparer, wall_clock=clock)
    session.start(fix())
    await session.wait_idle()

    clock.now += 61
    session.report(fix())
    await session.wait_idle()
    assert session.stopped_reason == "quota"

    clock.now += 3600
    session.report(fix())
    await session.wait_idle()
    assert len(preparer.calls) == 2  # 新的恢復時間還沒到，不再試

    clock.now += 3601
    session.report(fix())
    await session.wait_idle()
    assert session.stopped_reason is None
    assert len(preparer.calls) == 3


async def test_a_reset_time_already_in_the_past_does_not_cause_a_retry_on_every_report(tmp_path):
    clock = WallClock()
    preparer = FakePreparer(
        tmp_path,
        [
            QuotaExceededError("limit", resets_at=clock.now - 100),
            QuotaExceededError("limit"),
            ["A"],
        ],
    )
    session = TourSession(preparer, wall_clock=clock, quota_retry_after_s=900)
    session.start(fix())
    await session.wait_idle()

    for _ in range(5):
        clock.now += 10
        session.report(fix())
        await session.wait_idle()

    assert len(preparer.calls) == 1  # 過期的時間當作不知道，一樣等冷卻


async def test_the_call_limit_never_recovers_by_itself(tmp_path):
    clock = WallClock()
    preparer = FakePreparer(tmp_path, [LlmBudgetExhaustedError("budget"), ["A"]])
    session = TourSession(preparer, wall_clock=clock, quota_retry_after_s=1)
    session.start(fix())
    await session.wait_idle()

    clock.now += 10_000
    session.report(fix(north_of(START, 1000)))
    await session.wait_idle()

    assert session.stopped_reason == "llm_budget"
    assert len(preparer.calls) == 1


async def test_ending_a_tour_returns_what_happened_in_it(tmp_path):
    clock = WallClock()
    session = TourSession(FakePreparer(tmp_path, [["A", "B"]]), wall_clock=clock)
    session.start(fix())
    await session.wait_idle()
    clock.now += 600

    recap = session.end()

    assert recap.started_at == 1_000_000.0
    assert recap.ended_at == 1_000_600.0
    assert recap.narrations == 2
    assert recap.stopped_reason is None
    assert session.end() is None  # 沒有進行中的旅程


async def test_only_what_the_app_finished_playing_counts_as_told(tmp_path):
    preparer = FakePreparer(tmp_path, [["A", "B"], ["C"]])
    session = TourSession(preparer, reprepare_distance_m=100, journey=JourneyMemory(None))
    session.start(fix())
    await session.wait_idle()

    assert session.mark_played("wiki:A") is True  # A 播完了；B 被 App 丟掉，沒播
    session.report(fix(north_of(START, 200)))
    await session.wait_idle()

    second = preparer.calls[1]
    assert second["recent_topics"] == ("A",)
    assert set(second["told_before"]) == {"wiki:A"}
    assert {"wiki:A", "wiki:B"} <= second["exclude_ids"]  # 這趟已準備過的都不再準備


async def test_marking_an_unknown_narration_is_ignored(tmp_path):
    session = TourSession(FakePreparer(tmp_path, [["A"]]), journey=JourneyMemory(None))
    session.start(fix())
    await session.wait_idle()

    assert session.mark_played("wiki:不存在") is False
    assert session.mark_played("wiki:A") is True
    assert session.mark_played("wiki:A") is True  # 重送也沒事


async def test_a_second_start_soon_after_continues_the_trip_and_does_not_repeat_places(tmp_path):
    clock = WallClock()
    path = tmp_path / "journey.json"
    first = TourSession(
        FakePreparer(tmp_path, [["A"]]), wall_clock=clock, journey=JourneyMemory(path)
    )
    first.start(fix())
    await first.wait_idle()
    first.mark_played("wiki:A")

    clock.now += 3600  # App 被關掉，主機也重啟，一小時後重開 App 再按出發
    preparer = FakePreparer(tmp_path, [["B"]])
    second = TourSession(preparer, wall_clock=clock, journey=JourneyMemory(path))
    outcome = second.start(fix())
    await second.wait_idle()

    assert outcome.resumed is True
    assert preparer.calls[0]["recent_topics"] == ("A",)
    assert "wiki:A" in preparer.calls[0]["exclude_ids"]


async def test_the_report_of_a_resumed_trip_covers_the_whole_trip(tmp_path):
    clock = WallClock()
    path = tmp_path / "journey.json"
    first = TourSession(FakePreparer(tmp_path, []), wall_clock=clock, journey=JourneyMemory(path))
    first.start(fix())
    await first.wait_idle()
    trip_started = clock.now

    clock.now += 1800
    second = TourSession(FakePreparer(tmp_path, []), wall_clock=clock, journey=JourneyMemory(path))
    second.start(fix())
    await second.wait_idle()
    clock.now += 600

    assert second.end().started_at == trip_started


async def test_a_trip_left_open_for_too_long_is_handed_back_when_a_new_one_starts(tmp_path):
    clock = WallClock()
    path = tmp_path / "journey.json"
    first = TourSession(
        FakePreparer(tmp_path, [["A"]]), wall_clock=clock, journey=JourneyMemory(path)
    )
    first.start(fix())
    await first.wait_idle()
    first.mark_played("wiki:A")
    first.report(fix())  # 最後一次活動
    last_activity = clock.now

    clock.now += 3 * 3600
    second = TourSession(FakePreparer(tmp_path, []), wall_clock=clock, journey=JourneyMemory(path))
    outcome = second.start(fix())

    assert outcome.resumed is False
    assert outcome.abandoned.started_at == 1_000_000.0
    assert outcome.abandoned.ended_at == last_activity
    assert outcome.abandoned.narrations == 1


async def test_pressing_end_closes_the_trip_in_the_journey(tmp_path):
    clock = WallClock()
    journey = JourneyMemory(None)
    session = TourSession(FakePreparer(tmp_path, [["A"]]), wall_clock=clock, journey=journey)
    session.start(fix())
    await session.wait_idle()
    session.mark_played("wiki:A")

    session.end()
    outcome = session.start(fix())

    assert outcome.resumed is False
    assert outcome.abandoned is None


async def test_a_quota_hit_trips_the_shared_gate_so_questions_stop_too(tmp_path):
    clock = WallClock()
    gate = QuotaGate(wall_clock=clock)
    preparer = FakePreparer(tmp_path, [QuotaExceededError("limit", resets_at=clock.now + 3600)])
    session = TourSession(preparer, quota=gate, wall_clock=clock)

    session.start(fix())
    await session.wait_idle()

    assert gate.blocked()


async def test_a_gate_tripped_elsewhere_stops_preparing_until_it_recovers(tmp_path):
    clock = WallClock()
    gate = QuotaGate(wall_clock=clock)
    gate.trip(resets_at=clock.now + 3600)  # 問答先撞到額度
    preparer = FakePreparer(tmp_path, [["A"]])
    session = TourSession(preparer, quota=gate, wall_clock=clock)

    session.start(fix())
    await session.wait_idle()

    assert session.stopped_reason == "quota"
    assert preparer.calls == []  # 沒有再呼叫 Claude

    clock.now += 3601
    session.report(fix())
    await session.wait_idle()

    assert session.stopped_reason is None
    assert [e.name for e in session.narrations_after(0)] == ["A"]


async def test_a_gate_tripped_in_the_middle_of_a_tour_stops_the_next_preparation(tmp_path):
    clock = WallClock()
    gate = QuotaGate(wall_clock=clock)
    preparer = FakePreparer(tmp_path, [["A"], ["B"]])
    session = TourSession(preparer, quota=gate, wall_clock=clock, reprepare_distance_m=100)
    session.start(fix())
    await session.wait_idle()

    gate.trip(resets_at=clock.now + 3600)
    session.report(fix(north_of(START, 500)))
    await session.wait_idle()

    assert session.stopped_reason == "quota"
    assert len(preparer.calls) == 1


async def test_a_new_tour_does_not_clear_a_quota_that_is_still_exhausted(tmp_path):
    clock = WallClock()
    gate = QuotaGate(wall_clock=clock)
    gate.trip(resets_at=clock.now + 3600)
    preparer = FakePreparer(tmp_path, [["A"]])
    session = TourSession(preparer, quota=gate, wall_clock=clock)

    session.start(fix())
    session.end()
    session.start(fix())
    await session.wait_idle()

    assert session.stopped_reason == "quota"
    assert preparer.calls == []


async def test_a_question_probing_the_gate_first_does_not_lose_the_blocked_preparation(tmp_path):
    clock = WallClock()
    gate = QuotaGate(wall_clock=clock)
    gate.trip(resets_at=clock.now + 3600)
    preparer = FakePreparer(tmp_path, [["A"]])
    session = TourSession(preparer, quota=gate, wall_clock=clock)
    session.start(fix())  # 被閘門擋下，沒有準備
    await session.wait_idle()

    clock.now += 3601
    assert gate.admit()  # 問答搶先探測，閘門被它打開
    session.report(fix())  # 人沒移動，但該準備的還沒準備
    await session.wait_idle()

    assert [e.name for e in session.narrations_after(0)] == ["A"]


async def test_a_published_narration_has_the_start_of_every_unit_even_when_it_came_from_cache(
    tmp_path,
):
    import wave

    import numpy as np

    item = narration("A", tmp_path)
    pcm = np.concatenate([np.full(1000, 9000), np.zeros(500), np.full(1000, 9000)]).astype("<i2")
    with wave.open(str(item.wav_path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(1000)
        f.writeframes(pcm.tobytes())
    session = TourSession(FakePreparer(tmp_path, [[item]]))

    session.start(fix())
    await session.wait_idle()

    [event] = session.narrations_after(0)
    assert event.unit_starts == (0.0, 1.5)


async def test_a_question_probing_the_quota_first_does_not_lose_the_blocked_preparation(
    tmp_path,
):
    clock = WallClock()
    gate = QuotaGate(wall_clock=clock)
    preparer = FakePreparer(
        tmp_path, [QuotaExceededError("limit", resets_at=clock.now + 3600), ["A"]]
    )
    session = TourSession(preparer, quota=gate, wall_clock=clock)
    session.start(fix())
    await session.wait_idle()
    assert session.stopped_reason == "quota"

    clock.now += 3601
    assert gate.admit()  # 問答先探測成功，閘門被它打開
    session.report(fix())  # 人沒移動，但該準備的還沒準備
    await session.wait_idle()

    assert [e.name for e in session.narrations_after(0)] == ["A"]


async def tour_with(tmp_path, names, **kwargs):
    preparer = FakePreparer(tmp_path, [names, *kwargs.pop("later", [])])
    session = TourSession(preparer, journey=JourneyMemory(None), **kwargs)
    session.start(fix())
    await session.wait_idle()
    return preparer, session


def voices_of(session, after=0):
    return [(e.name, e.voice) for e in session.narrations_after(after)]


async def test_each_narration_and_the_session_say_which_voice_they_are(tmp_path):
    _, session = await tour_with(tmp_path, ["A"])

    assert session.voice_key == "F2@1.2"
    assert voices_of(session) == [("A", "F2@1.2")]


async def test_switching_withdraws_unplayed_narrations_and_redoes_them_in_the_new_voice(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A", "B", "C"])
    session.mark_played("wiki:A")

    session.change_voice("M1@1.2", playing_id="wiki:B")  # B 正在播、會播完
    await session.wait_idle()

    assert preparer.revoiced == [["wiki:C"]]
    assert len(preparer.calls) == 1  # 沒有重新準備（不會找 Claude 寫稿）
    assert [(e.seq, e.name, e.voice) for e in session.narrations_after(0)] == [
        (1, "A", "F2@1.2"),
        (2, "B", "F2@1.2"),
        (4, "C", "M1@1.2"),  # 同一個景點 id，以新的 seq 發布
    ]
    assert session.voice_key == "M1@1.2"


async def test_a_withdrawn_narration_is_gone_until_it_is_redone(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A"])
    preparer.revoice_gate = asyncio.Event()

    session.change_voice("M1@1.2")
    await asyncio.sleep(0)

    assert session.narrations_after(0) == []
    assert session.audio_path("wiki:A") is None
    assert session.preparing is True
    preparer.revoice_gate.set()
    await session.wait_idle()
    assert voices_of(session) == [("A", "M1@1.2")]


async def test_switching_without_a_tour_only_changes_the_voice(tmp_path):
    preparer = FakePreparer(tmp_path)
    session = TourSession(preparer)

    session.change_voice("M1@1.2")

    assert preparer.voice_key == "M1@1.2"
    assert preparer.revoiced == []
    assert session.preparing is False


async def test_switching_to_the_same_voice_withdraws_nothing(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A"])

    session.change_voice("F2@1.2")
    await session.wait_idle()

    assert preparer.revoiced == []
    assert voices_of(session) == [("A", "F2@1.2")]


async def test_withdrawn_places_stay_excluded_even_if_redoing_them_fails(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A"], later=[["B"]], reprepare_distance_m=100)
    preparer.revoice_error = RuntimeError("合成失敗")

    session.change_voice("M1@1.2")
    await session.wait_idle()
    session.report(fix(north_of(START, 200)))
    await session.wait_idle()

    # 重新排序會讓指紋對不上而重寫稿：撤下的地方這趟不再準備，不多耗 Claude
    assert "wiki:A" in preparer.calls[1]["exclude_ids"]
    assert voices_of(session) == [("B", "M1@1.2")]


async def test_narrations_of_a_running_preparation_follow_the_switch(tmp_path):
    preparer = FakePreparer(tmp_path, [["A", "B"]])
    preparer.report_progressively = True
    preparer.gate_after_first = asyncio.Event()
    session = TourSession(preparer, journey=JourneyMemory(None))
    session.start(fix())
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    assert voices_of(session) == [("A", "F2@1.2")]

    session.change_voice("M1@1.2")
    preparer.gate_after_first.set()  # 這一批做完：B 用新聲音，最後回傳的整批裡還有舊聲音的 A
    await session.wait_idle()

    # 舊聲音的 A 不會因為整批回傳又被發布；這一批做完後 A 重做成新聲音
    assert voices_of(session) == [("B", "M1@1.2"), ("A", "M1@1.2")]
    assert preparer.revoiced == [["wiki:A"]]


async def test_a_new_voice_narration_from_the_running_preparation_is_published(tmp_path):
    preparer = FakePreparer(tmp_path, [["A"]])
    preparer.gate = asyncio.Event()
    session = TourSession(preparer, journey=JourneyMemory(None))
    session.start(fix())
    await asyncio.sleep(0)

    session.change_voice("M1@1.2")  # 寫稿中換聲音：寫完直接用新聲音合成
    preparer.gate.set()
    await session.wait_idle()

    assert voices_of(session) == [("A", "M1@1.2")]
    assert preparer.revoiced == []


async def test_the_last_of_several_quick_switches_wins(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A"])
    preparer.revoice_gate = asyncio.Event()

    session.change_voice("M1@1.2")
    await asyncio.sleep(0)  # 開始用 M1 重做
    session.change_voice("M2@1.2")
    preparer.revoice_gate.set()
    await session.wait_idle()

    # 重做途中又換了：以最後一次為準
    assert voices_of(session) == [("A", "M2@1.2")]


async def test_switching_away_and_back_does_not_get_the_place_stuck(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A"])

    session.change_voice("M1@1.2")
    await session.wait_idle()
    session.change_voice("F2@1.2")
    await session.wait_idle()

    assert voices_of(session) == [("A", "F2@1.2")]
    assert preparer.revoiced == [["wiki:A"], ["wiki:A"]]


async def test_what_was_played_before_a_switch_is_still_told_once(tmp_path):
    preparer, session = await tour_with(
        tmp_path, ["A", "B"], later=[["C"]], reprepare_distance_m=100
    )
    session.mark_played("wiki:A")

    session.change_voice("M1@1.2")
    await session.wait_idle()
    session.mark_played("wiki:B")  # 新聲音的 B 播完
    session.report(fix(north_of(START, 200)))
    await session.wait_idle()

    assert preparer.calls[1]["recent_topics"] == ("A", "B")
    assert voices_of(session, after=0) == [("A", "F2@1.2"), ("B", "M1@1.2"), ("C", "M1@1.2")]


async def test_ending_the_tour_drops_pending_redos(tmp_path):
    preparer, session = await tour_with(tmp_path, ["A"])
    preparer.revoice_gate = asyncio.Event()
    session.change_voice("M1@1.2")
    await asyncio.sleep(0)

    session.end()
    preparer.revoice_gate.set()
    await session.wait_idle()
    session.start(fix())
    await session.wait_idle()

    assert session.narrations_after(0) == []


async def test_a_preparation_that_stops_the_tour_still_lets_the_redo_run(tmp_path):
    preparer, session = await tour_with(
        tmp_path, ["A"], later=[LlmBudgetExhaustedError("budget")], reprepare_distance_m=100
    )
    preparer.gate = asyncio.Event()
    session.report(fix(north_of(START, 200)))
    await asyncio.sleep(0)

    session.change_voice("M1@1.2")  # 準備進行中換聲音，這次準備隨後用完 Claude 次數
    preparer.gate.set()
    await session.wait_idle()

    assert session.stopped_reason == "llm_budget"
    assert voices_of(session) == [("A", "M1@1.2")]  # 重做不呼叫 Claude：照樣做
