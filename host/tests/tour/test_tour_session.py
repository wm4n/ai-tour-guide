import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.narration.preparer import PreparedNarration
from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode
from buddy_host.places.models import Location
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

    async def prepare(self, location, *, exclude_ids=(), traveler=None, **_):
        self.calls.append(
            {"location": location, "exclude_ids": set(exclude_ids), "traveler": traveler}
        )
        self.running += 1
        self.max_running = max(self.max_running, self.running)
        try:
            if self.gate:
                await self.gate.wait()
            result = self.results.pop(0) if self.results else []
            if isinstance(result, Exception):
                raise result
            return [narration(n, self.tmp_path) if isinstance(n, str) else n for n in result]
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
