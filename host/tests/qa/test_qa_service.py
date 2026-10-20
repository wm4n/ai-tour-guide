import asyncio
import threading
from datetime import datetime, timedelta, timezone

import pytest
from qa_fakes import FakeSpeech

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import LlmError, QuotaExceededError
from buddy_host.llm.models import ForbiddenModelError, LlmResult, Purpose
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.prompt import ScriptContext
from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode
from buddy_host.places.models import Candidate, Location
from buddy_host.qa.photos import PhotoRejected, PhotoStore
from buddy_host.qa.service import PhotosUnavailable, QaService
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix

HERE = Location(25.056, 121.51, heading_deg=0.0)
TAIPEI = timezone(timedelta(hours=8))
TRAVELER = TravelerContext(
    TravelMode.WALKING, Companions.SOLO, False, datetime(2026, 10, 20, 15, 0, tzinfo=TAIPEI)
)
FIX = TourFix(HERE, TRAVELER)


class FakeLlm:
    """依序回傳排好的結果（例外就拋出）；`tools` 在回答中依序回報；`hold` 讓測試卡住呼叫。"""

    def __init__(
        self,
        results=("好的，是拜城隍爺。",),
        tools=(),
        hold: asyncio.Event | None = None,
        events=(),
    ):
        self.results = list(results)
        self.tools = tools
        self.hold = hold
        self.events = events  # 依序：字串＝串流文字、("tool", 名稱)、asyncio.Event＝等它
        self.requests = []

    async def run(self, request, on_text=None, on_tool=None):
        self.requests.append(request)
        for event in self.events:
            if isinstance(event, asyncio.Event):
                await event.wait()
            elif isinstance(event, tuple):
                on_tool(event[1])
            else:
                on_text(event)
        for tool in self.tools:
            if on_tool:
                on_tool(tool)
        if self.hold:
            await self.hold.wait()
        result = self.results.pop(0) if self.results else "好的。"
        if isinstance(result, BaseException):
            raise result
        return LlmResult(result, "claude-sonnet-5-5", {}, {}, {}, 10)


class FakeNearby:
    def __init__(self, places=(), error: BaseException | None = None, delay: float = 0.0):
        self.places = list(places)
        self.error = error
        self.delay = delay
        self.calls = []

    async def nearby(self, location, *, limit=5):
        self.calls.append((location, limit))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return self.places


def temple() -> ScriptContext:
    return ScriptContext(
        candidate=Candidate("wiki:霞海城隍廟", "霞海城隍廟", 25.0561, 121.5100, {"tourism": "x"}),
        wiki_extract="霞海城隍廟主祀城隍爺。",
        distance_m=15.0,
        bearing_relative_deg=0.0,
    )


class Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def persona(tmp_path):
    path = tmp_path / "buddy.md"
    path.write_text("你是小花。", encoding="utf-8")
    return path


def make(persona, llm=None, nearby=None, clock=None, journey=None, speech=None, **kw):
    clock = clock or Clock()
    parts = dict(
        llm=llm or FakeLlm(),
        nearby=nearby or FakeNearby([temple()]),
        quota=QuotaGate(wall_clock=clock),
        journey=journey or JourneyMemory(None),
        speech=speech or FakeSpeech(),
        clock=clock,
    )
    service = QaService(
        parts["llm"],
        parts["nearby"],
        parts["speech"],
        persona_path=persona,
        out_dir=persona.parent / "qa",
        quota=parts["quota"],
        journey=parts["journey"],
        **kw,
    )
    return service, parts


async def ask_and_wait(service, question="那間廟拜的是誰？", fix=FIX, **kw):
    answer_id = service.ask(question, fix, **kw)
    await service.wait_idle()
    return service.answer(answer_id)


async def test_an_answer_starts_as_answering_and_ends_done_with_the_text(persona):
    hold = asyncio.Event()
    service, _ = make(persona, llm=FakeLlm(hold=hold))

    answer_id = service.ask("那間廟拜的是誰？", FIX)
    await asyncio.sleep(0)
    pending = service.answer(answer_id)
    assert (pending.status, pending.text, pending.reason) == ("answering", "", None)

    hold.set()
    await service.wait_idle()

    done = service.answer(answer_id)
    assert (done.status, done.text, done.reason) == ("done", "好的，是拜城隍爺。", None)


async def test_the_answer_text_is_stripped(persona):
    service, _ = make(persona, llm=FakeLlm(["  \n拜城隍爺。\n"]))

    answer = await ask_and_wait(service)

    assert answer.text == "拜城隍爺。"


async def test_unknown_answer_ids_are_none(persona):
    service, _ = make(persona)

    assert service.answer("nope") is None


async def test_the_request_has_persona_question_nearby_facts_and_journey(persona):
    journey = JourneyMemory(None)
    journey.begin(1000.0)
    journey.record_told(1010.0, "wiki:迪化街", "迪化街", "迪化街的稿子")
    llm = FakeLlm()
    nearby = FakeNearby([temple()])
    service, _ = make(persona, llm=llm, nearby=nearby, journey=journey)

    await ask_and_wait(service)

    [request] = llm.requests
    assert request.purpose is Purpose.QA and request.model == "sonnet"
    assert request.system_prompt.startswith("你是小花。")
    assert "那間廟拜的是誰？" in request.prompt
    assert "霞海城隍廟主祀城隍爺。" in request.prompt  # 附近景點資料
    assert "迪化街" in request.prompt  # 旅程摘要
    assert "走路" in request.prompt or "走" in request.prompt  # 旅人狀態
    assert nearby.calls[0][0] == HERE


async def test_the_persona_is_re_read_for_every_question(persona):
    llm = FakeLlm()
    service, _ = make(persona, llm=llm)
    await ask_and_wait(service)

    persona.write_text("你是小葉。", encoding="utf-8")
    await ask_and_wait(service)

    assert [r.system_prompt.split("\n")[0] for r in llm.requests] == ["你是小花。", "你是小葉。"]


async def test_asking_for_more_carries_what_was_just_told_and_only_what_was_played(persona):
    journey = JourneyMemory(None)
    journey.begin(1000.0)
    journey.record_told(1010.0, "wiki:迪化街", "迪化街", "迪化街的稿子")  # 播完才會記
    llm = FakeLlm()
    service, _ = make(persona, llm=llm, journey=journey)

    await ask_and_wait(service, "再多說一點", more=True)

    assert "迪化街的稿子" in llm.requests[0].prompt


async def test_each_question_is_a_fresh_conversation(persona):
    llm = FakeLlm()
    service, _ = make(persona, llm=llm)

    await ask_and_wait(service, "第一題")
    await ask_and_wait(service, "第二題")

    assert len(llm.requests) == 2
    assert "第一題" not in llm.requests[1].prompt


@pytest.mark.parametrize(
    ("tool", "searching"), [("WebSearch", True), ("WebFetch", True), ("Read", False)]
)
async def test_using_a_web_tool_is_reported_while_answering(persona, tool, searching):
    hold = asyncio.Event()
    service, _ = make(persona, llm=FakeLlm(tools=[tool], hold=hold))

    answer_id = service.ask("這間店現在有開嗎？", FIX)
    await asyncio.sleep(0)

    assert service.answer(answer_id).searching_web is searching
    hold.set()
    await service.wait_idle()
    assert service.answer(answer_id).status == "done"


async def test_a_quota_hit_fails_the_answer_and_stops_further_questions(persona):
    clock = Clock()
    llm = FakeLlm([QuotaExceededError("limit", resets_at=clock.now + 3600), "不該被呼叫"])
    service, parts = make(persona, llm=llm, clock=clock)

    first = await ask_and_wait(service)
    second = await ask_and_wait(service)

    assert (first.status, first.reason) == ("failed", "quota")
    assert (second.status, second.reason) == ("failed", "quota")
    assert len(llm.requests) == 1  # 第二題連 Claude 都沒呼叫
    assert parts["quota"].blocked()


async def test_questions_resume_by_themselves_once_the_limit_resets(persona):
    clock = Clock()
    llm = FakeLlm([QuotaExceededError("limit", resets_at=clock.now + 3600), "恢復了。"])
    service, _ = make(persona, llm=llm, clock=clock)
    await ask_and_wait(service)

    clock.now += 3601
    answer = await ask_and_wait(service)

    assert (answer.status, answer.text) == ("done", "恢復了。")


async def test_a_probe_that_is_still_rejected_blocks_again(persona):
    clock = Clock()
    llm = FakeLlm(
        [
            QuotaExceededError("limit", resets_at=clock.now + 60),
            QuotaExceededError("limit", resets_at=clock.now + 7200),
        ]
    )
    service, parts = make(persona, llm=llm, clock=clock)
    await ask_and_wait(service)
    clock.now += 61

    probe = await ask_and_wait(service)

    assert (probe.status, probe.reason) == ("failed", "quota")
    assert parts["quota"].blocked()


async def test_a_gate_tripped_elsewhere_blocks_questions_without_calling_claude(persona):
    clock = Clock()
    llm = FakeLlm()
    service, parts = make(persona, llm=llm, clock=clock)
    parts["quota"].trip(resets_at=clock.now + 3600)  # 主動介紹先撞到額度

    answer = await ask_and_wait(service)

    assert (answer.status, answer.reason) == ("failed", "quota")
    assert llm.requests == []


async def test_the_call_limit_is_reported_apart_from_the_quota_and_does_not_trip_the_gate(persona):
    llm = FakeLlm([LlmBudgetExhaustedError("budget")])
    service, parts = make(persona, llm=llm)

    answer = await ask_and_wait(service)

    assert (answer.status, answer.reason) == ("failed", "llm_budget")
    assert not parts["quota"].tripped


async def test_a_forbidden_model_is_reported(persona):
    service, _ = make(persona, llm=FakeLlm([ForbiddenModelError("fable")]))

    answer = await ask_and_wait(service)

    assert (answer.status, answer.reason) == ("failed", "forbidden_model")


@pytest.mark.parametrize("failure", [LlmError("boom"), RuntimeError("boom"), "   "])
async def test_other_failures_and_empty_answers_fail_with_a_generic_reason(persona, failure):
    service, parts = make(persona, llm=FakeLlm([failure]))

    answer = await ask_and_wait(service)

    assert (answer.status, answer.reason) == ("failed", "error")
    assert not parts["quota"].tripped


async def test_a_failed_nearby_lookup_does_not_stop_the_answer(persona):
    llm = FakeLlm()
    service, _ = make(persona, llm=llm, nearby=FakeNearby(error=RuntimeError("overpass down")))

    answer = await ask_and_wait(service)

    assert answer.status == "done"
    assert "附近沒有查到" in llm.requests[0].prompt


async def test_a_slow_nearby_lookup_is_given_up_on(persona):
    llm = FakeLlm()
    nearby = FakeNearby([temple()], delay=5)
    service, _ = make(persona, llm=llm, nearby=nearby, nearby_timeout_s=0.01)

    answer = await ask_and_wait(service)

    assert answer.status == "done"
    assert "附近沒有查到" in llm.requests[0].prompt


async def test_only_the_most_recent_answers_are_kept(persona):
    service, _ = make(persona, keep=2)

    ids = [service.ask(f"問題{i}", FIX) for i in range(3)]
    await service.wait_idle()

    assert service.answer(ids[0]) is None
    assert service.answer(ids[1]) is not None and service.answer(ids[2]) is not None


FIRST = "城隍爺是這裡的主神，香火很旺。"
SECOND = "你可以順便看看旁邊的老街。"


async def wait_until(predicate, timeout=2.0):
    for _ in range(int(timeout / 0.01)):
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("等不到條件成立")


async def test_the_first_segment_is_ready_before_the_answer_is_fully_written(persona):
    hold = asyncio.Event()
    service, _ = make(persona, llm=FakeLlm([FIRST + SECOND], events=[FIRST, hold, SECOND]))

    answer_id = service.ask("那間廟拜的是誰？", FIX)
    await wait_until(lambda: service.answer(answer_id).segments)

    early = service.answer(answer_id)
    assert early.status == "answering"  # Claude 還在寫
    assert [s.index for s in early.segments] == [0]
    assert service.audio_path(answer_id, 0).exists()

    hold.set()
    await service.wait_idle()
    assert [s.index for s in service.answer(answer_id).segments] == [0, 1]


async def test_every_segment_goes_through_the_speech_pipeline_and_can_be_downloaded(persona):
    speech = FakeSpeech(seconds=2.5)
    service, _ = make(persona, speech=speech, llm=FakeLlm([FIRST + SECOND], events=[FIRST, SECOND]))

    answer = await ask_and_wait(service)

    assert speech.texts == [FIRST, SECOND]  # 第一段單獨一段，其餘併在一起
    assert answer.status == "done"
    assert [(s.index, s.audio_seconds) for s in answer.segments] == [(0, 2.5), (1, 2.5)]
    assert all(service.audio_path(answer.id, i).read_bytes()[:4] == b"RIFF" for i in (0, 1))
    assert answer.text == FIRST + SECOND


async def test_the_answer_is_only_done_once_every_segment_is_made(persona):
    service, _ = make(persona, llm=FakeLlm([FIRST + SECOND], events=[FIRST, SECOND]))

    answer_id = service.ask("問題", FIX)
    await asyncio.sleep(0)
    assert service.answer(answer_id).status == "answering"
    await service.wait_idle()

    assert service.answer(answer_id).status == "done"


async def test_a_segment_that_fails_the_check_is_skipped_and_the_rest_still_play(persona):
    speech = FakeSpeech(skip=[FIRST])
    service, _ = make(persona, speech=speech, llm=FakeLlm([FIRST + SECOND], events=[FIRST, SECOND]))

    answer = await ask_and_wait(service)

    assert answer.status == "done"
    assert [s.index for s in answer.segments] == [0]  # 編號連續，App 不會以為少了一段
    assert service.audio_path(answer.id, 0) is not None


async def test_an_engine_crash_on_one_segment_only_skips_that_segment(persona):
    speech = FakeSpeech(explode=[FIRST])
    service, _ = make(persona, speech=speech, llm=FakeLlm([FIRST + SECOND], events=[FIRST, SECOND]))

    answer = await ask_and_wait(service)

    assert answer.status == "done" and len(answer.segments) == 1


async def test_when_every_segment_is_skipped_the_answer_fails_instead_of_staying_silent(persona):
    speech = FakeSpeech(skip=["好的，是拜城隍爺。"])
    service, _ = make(persona, speech=speech)

    answer = await ask_and_wait(service)

    assert (answer.status, answer.reason, answer.segments) == ("failed", "no_audio", [])


async def test_the_final_text_is_used_when_nothing_was_streamed(persona):
    speech = FakeSpeech()
    service, _ = make(persona, speech=speech, llm=FakeLlm([FIRST]))

    answer = await ask_and_wait(service)

    assert speech.texts == [FIRST]
    assert answer.status == "done"


async def test_a_lead_in_before_a_web_search_is_not_spoken(persona):
    speech = FakeSpeech()
    llm = FakeLlm(
        ["營業到晚上九點。"], events=["我來查一下。", ("tool", "WebSearch"), "營業到晚上九點。"]
    )
    service, _ = make(persona, speech=speech, llm=llm)

    answer = await ask_and_wait(service)

    assert speech.texts == ["營業到晚上九點。"]
    assert answer.searching_web is True


async def test_a_failure_after_some_segments_keeps_what_was_already_made(persona):
    hold = asyncio.Event()
    service, _ = make(persona, llm=FakeLlm([LlmError("斷線")], events=[FIRST, hold]))

    answer_id = service.ask("問題", FIX)
    await wait_until(lambda: service.answer(answer_id).segments)
    hold.set()  # 第一段做好之後，Claude 才斷線
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert (answer.status, answer.reason) == ("failed", "error")
    assert [s.index for s in answer.segments] == [0]  # 已經好的那一段還在，由 App 決定要不要播
    assert service.audio_path(answer_id, 0).exists()


async def test_unknown_segments_have_no_audio(persona):
    service, _ = make(persona)
    answer = await ask_and_wait(service)

    assert service.audio_path("nope", 0) is None
    assert service.audio_path(answer.id, 99) is None


async def test_the_audio_of_evicted_answers_is_deleted(persona):
    service, _ = make(persona, keep=1)
    first = await ask_and_wait(service)
    first_audio = service.audio_path(first.id, 0)
    assert first_audio.exists()

    await ask_and_wait(service)

    assert not first_audio.exists()
    assert service.audio_path(first.id, 0) is None


class SlowSpeech(FakeSpeech):
    """每次合成讓時鐘走 `took` 秒，用來量「收到問題 → 第一段可下載」。"""

    def __init__(self, clock, took):
        super().__init__()
        self.clock = clock
        self.took = took

    def run(self, text):
        self.clock.now += self.took
        return super().run(text)


async def test_the_delay_until_the_first_segment_is_recorded(persona, tmp_path):
    from buddy_host.llm.usage_log import UsageLog

    clock = Clock(100.0)
    log = UsageLog(tmp_path / "qa-latency.jsonl")
    service, _ = make(
        persona,
        speech=SlowSpeech(clock, took=7.5),
        llm=FakeLlm([FIRST + SECOND], events=[FIRST, SECOND]),
        latency_log=log,
        monotonic=clock,
    )

    answer = await ask_and_wait(service)

    assert answer.first_segment_seconds == 7.5  # 之後的段落不影響
    [entry] = log.read_all()
    assert entry["answer_id"] == answer.id and entry["first_segment_seconds"] == 7.5
    assert "timestamp" in entry


async def test_no_delay_is_recorded_when_nothing_was_ever_ready(persona, tmp_path):
    from buddy_host.llm.usage_log import UsageLog

    log = UsageLog(tmp_path / "qa-latency.jsonl")
    service, _ = make(
        persona, speech=FakeSpeech(skip=[FIRST]), llm=FakeLlm([FIRST]), latency_log=log
    )

    answer = await ask_and_wait(service)

    assert answer.first_segment_seconds is None
    assert log.read_all() == []


async def test_cancelling_the_service_does_not_leak_the_speaker_task(persona):
    hold = asyncio.Event()
    service, _ = make(persona, llm=FakeLlm([FIRST], events=[FIRST, hold]))
    baseline = len(asyncio.all_tasks())

    answer_id = service.ask("問題", FIX)
    await wait_until(lambda: service.answer(answer_id).segments)  # 合成的任務確實在跑了
    for task in list(service._tasks):
        task.cancel()
    await asyncio.sleep(0.05)

    assert len(asyncio.all_tasks()) == baseline  # 負責合成的任務也一起結束了


class BlockingSpeech(FakeSpeech):
    """第一次合成卡住直到被放行，用來模擬「合成到一半時答案失敗或被淘汰」。"""

    def __init__(self):
        super().__init__()
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, text):
        first = not self.texts
        if first:
            self.started.set()
            self.release.wait(5)
        return super().run(text)


async def test_a_failed_answer_stops_making_queued_segments_and_writes_nothing_late(persona):
    speech = BlockingSpeech()
    gate = asyncio.Event()
    llm = FakeLlm([LlmError("斷線")], events=[FIRST, SECOND * 4, gate])
    service, _ = make(persona, speech=speech, llm=llm)

    answer_id = service.ask("問題", FIX)
    await asyncio.to_thread(speech.started.wait, 5)  # 第一段正在合成
    gate.set()  # Claude 斷線 → 答案失敗
    await service.wait_idle()
    speech.release.set()  # 卡住的那一段這才做完
    await asyncio.sleep(0.1)

    answer = service.answer(answer_id)
    assert (answer.status, answer.reason) == ("failed", "error")
    assert speech.texts == [FIRST]  # 排隊中的後面幾段不再做
    assert answer.segments == []
    assert not (persona.parent / "qa" / answer_id / "seg-0.wav").exists()  # 失敗後不補寫檔案


async def test_an_evicted_answer_does_not_get_its_audio_written_afterwards(persona):
    speech = BlockingSpeech()
    service, _ = make(persona, speech=speech, keep=1, llm=FakeLlm([FIRST], events=[FIRST]))

    first_id = service.ask("問題一", FIX)
    await asyncio.to_thread(speech.started.wait, 5)
    service.ask("問題二", FIX)  # 淘汰第一個
    speech.release.set()
    await service.wait_idle()

    assert not (persona.parent / "qa" / first_id).exists()


async def test_an_unexpected_synthesis_bug_does_not_leave_the_answer_stuck(persona, monkeypatch):
    service, _ = make(persona, llm=FakeLlm([FIRST], events=[FIRST]))

    def broken(*args, **kwargs):
        raise TypeError("沒料到的 bug")

    monkeypatch.setattr(service, "_record_latency", broken)

    answer = await ask_and_wait(service)

    assert answer.status in ("done", "failed")  # 不會永遠停在 answering


async def test_the_speech_turn_is_held_for_the_whole_answer_and_always_given_back(persona):
    hold = asyncio.Event()
    speech = FakeSpeech()
    service, _ = make(persona, speech=speech, llm=FakeLlm([FIRST], events=[FIRST, hold]))

    answer_id = service.ask("問題", FIX)
    await wait_until(lambda: service.answer(answer_id).segments)

    [turn] = speech.turns  # Claude 還在寫下一段，優先權還在手上
    assert turn.ended is False

    hold.set()
    await service.wait_idle()
    assert turn.ended is True


async def test_the_speech_turn_is_given_back_when_the_answer_fails(persona):
    speech = FakeSpeech()
    service, _ = make(persona, speech=speech, llm=FakeLlm([LlmError("斷線")]))

    await ask_and_wait(service)

    assert [turn.ended for turn in speech.turns] == [True]


async def test_the_speech_turn_is_given_back_when_the_service_is_cancelled(persona):
    hold = asyncio.Event()
    speech = FakeSpeech()
    service, _ = make(persona, speech=speech, llm=FakeLlm([FIRST], events=[FIRST, hold]))
    answer_id = service.ask("問題", FIX)
    await wait_until(lambda: service.answer(answer_id).segments)

    for task in list(service._tasks):
        task.cancel()
    await asyncio.sleep(0.05)

    assert [turn.ended for turn in speech.turns] == [True]


async def test_a_question_blocked_by_the_quota_never_takes_a_turn(persona):
    speech = FakeSpeech()
    service, parts = make(persona, speech=speech)
    parts["quota"].trip(resets_at=parts["clock"].now + 3600)

    await ask_and_wait(service)

    assert speech.turns == []


JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def make_with_photos(persona, **kw):
    store = PhotoStore(persona.parent / "photos")
    service, parts = make(persona, photos=store, **kw)
    return service, parts, store


async def test_a_photo_question_saves_the_photo_and_hands_it_to_claude(persona):
    llm = FakeLlm()
    service, _, store = make_with_photos(persona, llm=llm)
    compass_fix = TourFix(Location(25.056, 121.51, heading_deg=270.0), TRAVELER)

    answer_id = service.ask_photo("這是什麼？", compass_fix, JPEG)
    await service.wait_idle()

    [saved] = list(store.directory.iterdir())
    [request] = llm.requests
    assert saved.read_bytes() == JPEG
    assert str(saved) in request.prompt
    assert request.allowed_tools == (f"Read(/{store.directory}/**)",)
    assert request.add_dirs == (store.directory,)
    assert "西" in request.prompt and "指南針" in request.prompt  # 拍照時的方向
    assert service.answer(answer_id).status == "done"


async def test_the_photo_is_kept_after_the_answer_until_the_retention_period_ends(persona):
    service, _, store = make_with_photos(persona)

    service.ask_photo("這是什麼？", FIX, JPEG)
    await service.wait_idle()

    assert len(list(store.directory.iterdir())) == 1


async def test_something_that_is_not_a_photo_is_refused_before_anything_starts(persona):
    llm = FakeLlm()
    service, _, store = make_with_photos(persona, llm=llm)

    with pytest.raises(PhotoRejected):
        service.ask_photo("這是什麼？", FIX, b"not an image")
    await service.wait_idle()

    assert llm.requests == []
    assert not store.directory.exists() or not list(store.directory.iterdir())


async def test_photo_questions_are_unavailable_without_a_photo_store(persona):
    service, _ = make(persona)

    assert service.photos_enabled is False
    with pytest.raises(PhotosUnavailable):
        service.ask_photo("這是什麼？", FIX, JPEG)


async def test_a_photo_question_goes_through_the_same_quota_gate(persona):
    llm = FakeLlm()
    service, parts, _ = make_with_photos(persona, llm=llm)
    parts["quota"].trip(resets_at=parts["clock"].now + 3600)

    answer_id = service.ask_photo("這是什麼？", FIX, JPEG)
    await service.wait_idle()

    assert service.answer(answer_id).reason == "quota"
    assert llm.requests == []


async def test_asking_any_question_clears_photos_past_their_retention(persona):
    import os

    clock = Clock(1_000_000.0)
    store = PhotoStore(persona.parent / "photos", retention_s=3600, clock=clock)
    old = store.save(JPEG)
    os.utime(old, (clock.now - 7200, clock.now - 7200))
    service, _ = make(persona, photos=store)

    await ask_and_wait(service)  # 一般問題，沒有拍照

    assert not old.exists()


async def test_purge_photos_reports_how_many_were_removed(persona):
    import os

    clock = Clock(1_000_000.0)
    store = PhotoStore(persona.parent / "photos", retention_s=60, clock=clock)
    old = store.save(JPEG)
    os.utime(old, (clock.now - 120, clock.now - 120))
    service, _ = make(persona, photos=store)

    assert service.purge_photos() == 1
    assert service.purge_photos() == 0


async def test_purge_photos_without_a_store_does_nothing(persona):
    service, _ = make(persona)

    assert service.purge_photos() == 0
