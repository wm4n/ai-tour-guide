"""問答搭配真正的 ClaudeCliClient（只把 `claude` 換成假的可執行檔）：確認整條線接得起來。"""

import sys
from pathlib import Path

import pytest
from qa_fakes import FakeSpeech

from buddy_host.llm.claude_cli import ClaudeCliClient, ClaudeSettings
from buddy_host.llm.quota import QuotaGate
from buddy_host.llm.usage_log import UsageLog
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.models import Location
from buddy_host.qa.service import QaService
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix

FAKE = Path(__file__).parents[1] / "llm" / "fake_claude.py"
FIX = TourFix(Location(25.056, 121.51, 0.0), TravelerContext())


class NoPlaces:
    async def nearby(self, location, *, limit=5):
        return []


@pytest.fixture
def service(tmp_path):
    (tmp_path / "claude-token").write_text("token", encoding="utf-8")
    persona = tmp_path / "buddy.md"
    persona.write_text("你是小花。", encoding="utf-8")
    client = ClaudeCliClient(ClaudeSettings.for_home(tmp_path, command=(sys.executable, str(FAKE))))
    return QaService(
        client,
        NoPlaces(),
        FakeSpeech(),
        persona_path=persona,
        out_dir=tmp_path / "qa",
        quota=QuotaGate(),
        journey=JourneyMemory(None),
    )


async def test_a_web_search_in_the_stream_reaches_the_answer_and_the_call_is_logged(
    service, tmp_path, monkeypatch
):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "tool")

    answer_id = service.ask("這間店現在有開嗎？", FIX)
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert (answer.status, answer.text, answer.searching_web) == (
        "done",
        "你好，這是串流回覆。",
        True,
    )
    [entry] = UsageLog(tmp_path / "usage.jsonl").read_all()
    assert entry["purpose"] == "qa" and entry["model_requested"] == "sonnet"


async def test_a_quota_rejection_from_claude_fails_the_answer(service, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "quota")

    answer_id = service.ask("這是什麼？", FIX)
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert (answer.status, answer.reason) == ("failed", "quota")


async def test_fable_showing_up_in_the_usage_is_refused(service, monkeypatch):
    monkeypatch.setenv("FAKE_CLAUDE_MODE", "fable")

    answer_id = service.ask("這是什麼？", FIX)
    await service.wait_idle()

    answer = service.answer(answer_id)
    assert (answer.status, answer.reason) == ("failed", "forbidden_model")
