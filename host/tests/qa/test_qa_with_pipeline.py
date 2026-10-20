"""問答搭配真正的 SpeechPipeline（合成器與辨識器是假的）：每一段都真的經過驗收。"""

import numpy as np
import pytest

from buddy_host.llm.models import LlmResult
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.models import Location
from buddy_host.qa.service import QaService
from buddy_host.speech.pipeline import PipelineConfig, SpeechPipeline
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix

FIX = TourFix(Location(25.056, 121.51, 0.0), TravelerContext())
GOOD = "城隍爺是這裡的主神，香火很旺。"
BAD = "你可以順便看看旁邊的老街。"


class FakeSynth:
    sample_rate = 1000

    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def synthesize(self, text, seed):
        self.calls.append((text, seed))
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
    pipeline = SpeechPipeline(synth, Recognizer(synth), config)
    service = QaService(
        StreamingLlm(),
        NoPlaces(),
        pipeline,
        persona_path=persona,
        out_dir=tmp_path / "qa",
        quota=QuotaGate(),
        journey=JourneyMemory(None),
    )
    return service, synth


async def test_each_segment_is_checked_and_the_one_that_never_passes_is_skipped(parts):
    service, synth = parts

    answer_id = service.ask("這是什麼？", FIX)
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert answer.status == "done"
    assert [s.index for s in answer.segments] == [0]  # BAD 換了 seed 還是不過，被跳過
    assert [seed for text, seed in synth.calls if text == GOOD] == [1]
    assert [seed for text, seed in synth.calls if text == BAD] == [1, 2]
    assert service.audio_path(answer_id, 0).exists()
