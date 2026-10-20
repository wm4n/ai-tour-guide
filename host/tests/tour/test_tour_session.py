import asyncio
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


def narration(name: str, tmp_path: Path) -> PreparedNarration:
    wav = tmp_path / f"{name}.wav"
    wav.write_bytes(b"RIFF")
    return PreparedNarration(
        f"wiki:{name}", name, f"{name}的稿子", wav, tmp_path / f"{name}.json", 31.5, 80.0,
        25.05, 121.51,
    )  # fmt: skip


class FakePreparer:
    """每次 prepare 依序回傳預先排好的結果；gate 讓測試卡住一次準備。"""

    def __init__(self, tmp_path: Path, results=None):
        self.tmp_path = tmp_path
        self.results = list(results or [])
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
            items = [narration(n, self.tmp_path) if isinstance(n, str) else n for n in result]
            if on_ready and self.report_progressively:
                for item in items:
                    on_ready(item)
                    if self.gate_after_first:
                        await self.gate_after_first.wait()
            return items
        finally:
            self.running -= 1


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
