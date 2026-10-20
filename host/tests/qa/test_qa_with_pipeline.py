"""問答搭配真正的 SpeechPipeline（合成器與辨識器是假的）：每一段都真的經過驗收。"""

import asyncio
import threading

import numpy as np
import pytest

from buddy_host.llm.models import LlmResult
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.models import Location
from buddy_host.qa.service import QaService
from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline
from buddy_host.speech.scheduler import SpeechScheduler
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix

FIX = TourFix(Location(25.056, 121.51, 0.0), TravelerContext())
GOOD = "城隍爺是這裡的主神，香火很旺。"
BAD = "你可以順便看看旁邊的老街。"


class FakeSynth:
    sample_rate = 1000

    def __init__(self):
        self.calls: list[tuple[str, int]] = []
        self.started: dict[str, threading.Event] = {}
        self.blocked: dict[str, threading.Event] = {}

    def block(self, text):
        self.started[text] = threading.Event()
        self.blocked[text] = threading.Event()

    def synthesize(self, text, seed):
        self.calls.append((text, seed))
        if text in self.started:
            self.started[text].set()
            self.blocked[text].wait(5)
        return np.full(len(text) * 10, 0.1, dtype=np.float32)


class Recognizer:
    """最後一次合成的是 BAD 時，轉寫出完全不同的話（驗收不過）。"""

    def __init__(self, synth):
        self.synth = synth

    def transcribe(self, audio, sample_rate):
        text, _ = self.synth.calls[-1]
        return "完全不一樣的話" if text == BAD else text


class StreamingLlm:
    async def run(self, request, on_text=None, on_tool=None):
        on_text(GOOD)
        on_text(BAD)
        return LlmResult(GOOD + BAD, "claude-sonnet-5-5", {}, {}, {}, 1)


class NoPlaces:
    async def nearby(self, location, *, limit=5):
        return []


@pytest.fixture
def parts(tmp_path):
    persona = tmp_path / "buddy.md"
    persona.write_text("你是小花。", encoding="utf-8")
    synth = FakeSynth()
    config = PipelineConfig(seeds=(1, 2), opening_extra_seeds=(), split_on_failure=False)
    scheduler = SpeechScheduler(SpeechPipeline(synth, Recognizer(synth), config))
    service = QaService(
        StreamingLlm(),
        NoPlaces(),
        scheduler.answers,
        persona_path=persona,
        out_dir=tmp_path / "qa",
        quota=QuotaGate(),
        journey=JourneyMemory(None),
    )
    return service, synth, scheduler, persona, tmp_path


async def test_each_segment_is_checked_and_the_one_that_never_passes_is_skipped(parts):
    service, synth, *_ = parts

    answer_id = service.ask("這是什麼？", FIX)
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert answer.status == "done"
    assert [s.index for s in answer.segments] == [0]  # BAD 換了 seed 還是不過，被跳過
    assert [seed for text, seed in synth.calls if text == GOOD] == [1]
    assert [seed for text, seed in synth.calls if text == BAD] == [1, 2]
    assert service.audio_path(answer_id, 0).exists()


OK2 = "旁邊還有一條很有名的老街。"
STORY_1, STORY_2 = "介紹的第一段。", "介紹的第二段。"


class GappedLlm:
    """先寫出第一句，Claude 停一下（例如在上網查），再寫第二句。"""

    def __init__(self, gap: asyncio.Event):
        self.gap = gap

    async def run(self, request, on_text=None, on_tool=None):
        on_text(GOOD)
        await self.gap.wait()
        on_text(OK2)
        return LlmResult(GOOD + OK2, "claude-sonnet-5-5", {}, {}, {}, 1)


async def test_the_narration_cannot_slip_in_while_claude_is_still_writing_the_answer(tmp_path):
    persona = tmp_path / "buddy.md"
    persona.write_text("你是小花。", encoding="utf-8")
    synth = FakeSynth()
    synth.block(STORY_1)
    scheduler = SpeechScheduler(
        SpeechPipeline(
            synth,
            Recognizer(synth),
            PipelineConfig(
                opening_extra_seeds=(),
            ),
        )
    )
    gap = asyncio.Event()
    service = QaService(
        GappedLlm(gap),
        NoPlaces(),
        scheduler.answers,
        persona_path=persona,
        out_dir=tmp_path / "qa",
        quota=QuotaGate(),
        journey=JourneyMemory(None),
    )

    story = threading.Thread(target=scheduler.narration.run, args=(f"{STORY_1}\n\n{STORY_2}",))
    story.start()
    await asyncio.to_thread(synth.started[STORY_1].wait, 5)  # 主動介紹正在合成第一個單位
    answer_id = service.ask("這是什麼？", FIX)
    for _ in range(500):
        if scheduler.pending_answers:
            break
        await asyncio.sleep(0.01)
    synth.blocked[STORY_1].set()  # 介紹的第一個單位做完，讓路給問答

    for _ in range(500):
        if service.answer(answer_id).segments:
            break
        await asyncio.sleep(0.01)
    await asyncio.sleep(0.15)  # Claude 還在寫第二句：介紹不可以趁機開始第二個單位
    assert [text for text, _ in synth.calls] == [STORY_1, GOOD]

    gap.set()
    await service.wait_idle()
    await asyncio.to_thread(story.join, 5)

    assert [text for text, _ in synth.calls] == [STORY_1, GOOD, OK2, STORY_2]
    assert service.answer(answer_id).status == "done"
