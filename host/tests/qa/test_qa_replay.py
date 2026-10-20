"""重播模式的假答案：不呼叫 Claude、不載入語音模型，桌上（模擬器）跑通 App 的問答流程。"""

import wave

import pytest

from buddy_host.llm.models import LlmRequest, Purpose
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.models import Location
from buddy_host.qa.replay import CannedLlm, NoNearby, ToneSpeech
from buddy_host.qa.service import QaService
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix

FIX = TourFix(Location(25.056, 121.51, 0.0), TravelerContext())


def request(prompt="那間廟拜的是誰？") -> LlmRequest:
    return LlmRequest(prompt, Purpose.QA)


async def test_the_canned_llm_streams_a_fixed_answer():
    chunks: list[str] = []

    result = await CannedLlm().run(request(), on_text=chunks.append)

    assert "".join(chunks) == result.text
    assert len(chunks) > 1 and result.text.count("。") >= 2


async def test_asking_about_the_web_reports_a_web_search():
    tools: list[str] = []

    await CannedLlm().run(request("這間店現在有開嗎？上網查一下"), on_tool=tools.append)

    assert tools == ["WebSearch"]


async def test_other_questions_do_not_search():
    tools: list[str] = []

    await CannedLlm().run(request(), on_tool=tools.append)

    assert tools == []


async def test_there_are_never_nearby_places():
    assert await NoNearby().nearby(Location(25.0, 121.5), limit=5) == []


def test_the_tone_speech_makes_audible_audio_for_each_segment():
    turn = ToneSpeech(seconds=0.5).begin()

    result = turn.run("任何一段文字。")
    turn.end()

    assert result.audio_seconds == pytest.approx(0.5, abs=0.01)
    assert abs(result.audio).max() > 0.05


async def test_the_whole_replay_answer_goes_through_the_real_service(tmp_path):
    persona = tmp_path / "buddy.md"
    persona.write_text("你是小花。", encoding="utf-8")
    service = QaService(
        CannedLlm(),
        NoNearby(),
        ToneSpeech(),
        persona_path=persona,
        out_dir=tmp_path / "qa",
        quota=QuotaGate(),
        journey=JourneyMemory(None),
    )

    answer_id = service.ask("這是什麼？", FIX)
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert answer.status == "done" and answer.segments
    with wave.open(str(service.audio_path(answer_id, 0))) as wav:
        assert wav.getframerate() > 0 and wav.getnframes() > 0
