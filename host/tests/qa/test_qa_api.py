import asyncio
import time

import pytest
from fastapi.testclient import TestClient

from buddy_host.app import create_app
from buddy_host.config import HostConfig
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import LlmResult
from buddy_host.narration.preparer import PreparedNarration
from buddy_host.qa.service import QaService

BODY = {
    "question": "那間廟拜的是誰？",
    "lat": 25.056,
    "lon": 121.51,
    "heading_deg": 200,
    "mode": "walking",
    "companions": "solo",
    "local_time": "2026-10-20T15:04:00+08:00",
}


class FakeLlm:
    def __init__(self, results=("拜城隍爺。",), tools=(), hold: asyncio.Event | None = None):
        self.results = list(results)
        self.tools = tools
        self.hold = hold
        self.requests = []

    async def run(self, request, on_text=None, on_tool=None):
        self.requests.append(request)
        for tool in self.tools:
            on_tool(tool)
        if self.hold:
            await self.hold.wait()
        result = self.results.pop(0) if self.results else "好的。"
        if isinstance(result, BaseException):
            raise result
        return LlmResult(result, "claude-sonnet-5-5", {}, {}, {}, 10)


class FakeNearby:
    async def nearby(self, location, *, limit=5):
        return []


class FakePreparer:
    def __init__(self, wav, results=()):
        self.wav = wav
        self.results = list(results)

    async def prepare(self, location, **_):
        result = self.results.pop(0) if self.results else None
        if isinstance(result, BaseException):
            raise result
        if result is None:
            return [
                PreparedNarration(
                    "wiki:迪化街",
                    "迪化街",
                    "迪化街的稿子",
                    self.wav,
                    self.wav,
                    30.0,
                    10.0,
                    25.05,
                    121.5,
                )
            ]
        return result


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "a.wav"
    path.write_bytes(b"RIFF....WAVEdata")
    return path


@pytest.fixture
def persona(tmp_path):
    path = tmp_path / "buddy.md"
    path.write_text("你是小花。", encoding="utf-8")
    return path


def build_client(tmp_path, wav, persona, llm, preparer=None, token="s3cret"):
    config = HostConfig(home=tmp_path, token=token)

    def factory(quota, journey):
        return QaService(llm, FakeNearby(), persona_path=persona, quota=quota, journey=journey)

    app = create_app(config, preparer=preparer or FakePreparer(wav), answerer_factory=factory)
    client = TestClient(app)
    if token:
        client.headers["X-Buddy-Token"] = token
    return client


@pytest.fixture
def llm():
    return FakeLlm()


@pytest.fixture
def client(tmp_path, wav, persona, llm):
    with build_client(tmp_path, wav, persona, llm) as client:
        yield client


def wait_for_answer(client, answer_id, statuses=("done", "failed")):
    for _ in range(100):
        body = client.get("/v1/qa/answer", params={"id": answer_id}).json()
        if body["status"] in statuses:
            return body
        time.sleep(0.02)
    raise AssertionError(f"答案一直沒好：{body}")


def wait_for_tour(client, count):
    for _ in range(100):
        body = client.get("/v1/tour/narrations").json()
        if len(body["narrations"]) >= count or body["stopped_reason"]:
            return body
        time.sleep(0.02)
    raise AssertionError(f"介紹一直沒好：{body}")


def test_qa_endpoints_require_the_token(tmp_path, wav, persona, llm):
    with build_client(tmp_path, wav, persona, llm) as bare:
        del bare.headers["X-Buddy-Token"]
        assert bare.post("/v1/qa/ask", json=BODY).status_code == 401
        assert bare.get("/v1/qa/answer", params={"id": "x"}).status_code == 401


def test_qa_is_unavailable_until_it_is_switched_on(tmp_path, wav):
    config = HostConfig(home=tmp_path)
    with TestClient(create_app(config, preparer=FakePreparer(wav))) as bare:
        assert bare.post("/v1/qa/ask", json=BODY).status_code == 503
        assert bare.get("/v1/qa/answer", params={"id": "x"}).status_code == 503


def test_ask_returns_an_id_and_the_answer_can_be_polled(client, llm):
    response = client.post("/v1/qa/ask", json=BODY)

    assert response.status_code == 200
    answer_id = response.json()["id"]
    body = wait_for_answer(client, answer_id)

    assert body == {
        "id": answer_id,
        "status": "done",
        "text": "拜城隍爺。",
        "searching_web": False,
        "reason": None,
    }
    assert "那間廟拜的是誰？" in llm.requests[0].prompt


def test_an_unknown_answer_id_is_404(client):
    assert client.get("/v1/qa/answer", params={"id": "nope"}).status_code == 404


@pytest.mark.parametrize(
    "patch",
    [
        {"question": ""},
        {"question": "   "},
        {"question": "問" * 501},
        {"lat": 91},
        {"lon": 181},
        {"heading_deg": 361},
    ],
)
def test_bad_questions_and_positions_are_rejected(client, patch):
    assert client.post("/v1/qa/ask", json={**BODY, **patch}).status_code == 422


def test_the_question_is_trimmed_and_traveler_fields_are_optional(client, llm):
    body = {"question": "  這是什麼？  ", "lat": 25.0, "lon": 121.5}

    answer_id = client.post("/v1/qa/ask", json=body).json()["id"]
    wait_for_answer(client, answer_id)

    assert "「這是什麼？」" in llm.requests[0].prompt


def test_the_app_can_see_that_claude_is_searching_the_web(tmp_path, wav, persona):
    hold = asyncio.Event()
    llm = FakeLlm(tools=["WebSearch"], hold=hold)
    with build_client(tmp_path, wav, persona, llm) as client:
        answer_id = client.post("/v1/qa/ask", json=BODY).json()["id"]

        body = wait_for_answer(client, answer_id, statuses=("answering",))
        for _ in range(100):
            body = client.get("/v1/qa/answer", params={"id": answer_id}).json()
            if body["searching_web"]:
                break
            time.sleep(0.02)

        assert (body["status"], body["searching_web"]) == ("answering", True)


def test_asking_for_more_follows_up_on_what_finished_playing(client, llm):
    client.post("/v1/tour/start", json=BODY)
    wait_for_tour(client, 1)

    first = client.post("/v1/qa/ask", json={**BODY, "more": True}).json()["id"]
    wait_for_answer(client, first)
    before_played = llm.requests[-1].prompt

    client.post("/v1/tour/played", json={"id": "wiki:迪化街"})  # App 回報播完了
    second = client.post("/v1/qa/ask", json={**BODY, "more": True}).json()["id"]
    wait_for_answer(client, second)

    assert "迪化街的稿子" not in before_played  # 只是準備好、還沒播完的不算
    assert "迪化街的稿子" in llm.requests[-1].prompt


def test_a_quota_hit_while_answering_stops_the_tour_preparation_too(tmp_path, wav, persona):
    llm = FakeLlm([QuotaExceededError("limit", resets_at=time.time() + 3600)])
    with build_client(tmp_path, wav, persona, llm) as client:
        answer = wait_for_answer(client, client.post("/v1/qa/ask", json=BODY).json()["id"])
        assert (answer["status"], answer["reason"]) == ("failed", "quota")

        client.post("/v1/tour/start", json=BODY)
        tour = client.get("/v1/tour/narrations").json()

        assert tour["stopped_reason"] == "quota"
        assert tour["narrations"] == []


def test_a_quota_hit_while_preparing_stops_questions_too(tmp_path, wav, persona):
    llm = FakeLlm()
    preparer = FakePreparer(wav, [QuotaExceededError("limit", resets_at=time.time() + 3600)])
    with build_client(tmp_path, wav, persona, llm, preparer=preparer) as client:
        client.post("/v1/tour/start", json=BODY)
        assert wait_for_tour(client, 1)["stopped_reason"] == "quota"

        answer = wait_for_answer(client, client.post("/v1/qa/ask", json=BODY).json()["id"])

        assert (answer["status"], answer["reason"]) == ("failed", "quota")
        assert llm.requests == []
