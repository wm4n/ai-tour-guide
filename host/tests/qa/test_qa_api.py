import asyncio
import base64
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from qa_fakes import FakeSpeech

from buddy_host.app import create_app
from buddy_host.config import HostConfig
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import LlmResult
from buddy_host.narration.preparer import DEFAULT_VOICE_KEY, PreparedNarration
from buddy_host.qa.photos import PhotoStore
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
        self.voice_key = DEFAULT_VOICE_KEY  # 介紹是預設聲音（PreparedNarration 的預設）

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


def build_client(tmp_path, wav, persona, llm, preparer=None, token="s3cret", photos=True):
    config = HostConfig(home=tmp_path, token=token)

    def factory(quota, journey):
        return QaService(
            llm,
            FakeNearby(),
            FakeSpeech(),
            persona_path=persona,
            out_dir=tmp_path / "qa",
            quota=quota,
            journey=journey,
            photos=PhotoStore(tmp_path / "photos", max_bytes=2000) if photos else None,
        )

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
        assert bare.get("/v1/qa/audio", params={"id": "x", "index": 0}).status_code == 401


def test_qa_is_unavailable_until_it_is_switched_on(tmp_path, wav):
    config = HostConfig(home=tmp_path)
    with TestClient(create_app(config, preparer=FakePreparer(wav))) as bare:
        assert bare.post("/v1/qa/ask", json=BODY).status_code == 503
        assert bare.get("/v1/qa/answer", params={"id": "x"}).status_code == 503
        assert bare.get("/v1/qa/audio", params={"id": "x", "index": 0}).status_code == 503


def test_ask_returns_an_id_and_the_answer_can_be_polled(client, llm):
    response = client.post("/v1/qa/ask", json=BODY)

    assert response.status_code == 200
    answer_id = response.json()["id"]
    body = wait_for_answer(client, answer_id)

    assert body == {
        "id": answer_id,
        "status": "done",
        "text": "拜城隍爺。",
        "segments": [{"index": 0, "audio_seconds": 2.0}],
        "first_segment_seconds": body["first_segment_seconds"],
        "searching_web": False,
        "reason": None,
    }
    assert body["first_segment_seconds"] >= 0
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


def test_each_segment_of_the_answer_can_be_downloaded(client):
    answer_id = client.post("/v1/qa/ask", json=BODY).json()["id"]
    wait_for_answer(client, answer_id)

    audio = client.get("/v1/qa/audio", params={"id": answer_id, "index": 0})

    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    assert audio.content[:4] == b"RIFF"


def test_a_segment_that_does_not_exist_is_404(client):
    answer_id = client.post("/v1/qa/ask", json=BODY).json()["id"]
    wait_for_answer(client, answer_id)

    assert client.get("/v1/qa/audio", params={"id": answer_id, "index": 5}).status_code == 404
    assert client.get("/v1/qa/audio", params={"id": "nope", "index": 0}).status_code == 404


def test_the_tour_report_includes_the_qa_delay(tmp_path, wav, persona):
    import json
    from datetime import UTC, datetime

    from buddy_host.llm.usage_log import UsageLog

    latency_log = tmp_path / "qa-latency.jsonl"
    reports = tmp_path / "reports"
    config = HostConfig(home=tmp_path)
    app = create_app(
        config,
        preparer=FakePreparer(wav),
        reports_dir=reports,
        qa_latency_log_path=latency_log,
    )
    with TestClient(app) as client:
        client.post("/v1/tour/start", json=BODY)
        UsageLog(latency_log).append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "answer_id": "a1",
                "first_segment_seconds": 6.5,
            }
        )

        client.post("/v1/tour/end")

    [path] = reports.glob("tour-*.json")
    assert json.loads(path.read_text(encoding="utf-8"))["qa"]["avg_first_segment_seconds"] == 6.5


JPEG_B64 = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 64).decode()


def test_ask_photo_requires_the_token(tmp_path, wav, persona, llm):
    with build_client(tmp_path, wav, persona, llm) as bare:
        del bare.headers["X-Buddy-Token"]
        body = {**BODY, "image_base64": JPEG_B64}
        assert bare.post("/v1/qa/ask-photo", json=body).status_code == 401


def test_a_photo_question_is_answered_like_any_other(client, llm, tmp_path):
    body = {**BODY, "question": "這是什麼？", "image_base64": JPEG_B64}

    response = client.post("/v1/qa/ask-photo", json=body)

    assert response.status_code == 200
    answer = wait_for_answer(client, response.json()["id"])
    assert answer["status"] == "done"
    [saved] = list((tmp_path / "photos").iterdir())
    assert str(saved) in llm.requests[0].prompt
    assert "指南針" in llm.requests[0].prompt


def test_the_question_defaults_to_what_is_this(client, llm):
    body = {key: value for key, value in BODY.items() if key != "question"}

    answer_id = client.post("/v1/qa/ask-photo", json={**body, "image_base64": JPEG_B64}).json()[
        "id"
    ]
    wait_for_answer(client, answer_id)

    assert "這是什麼" in llm.requests[0].prompt


def test_a_bad_photo_is_refused(client):
    not_base64 = {**BODY, "image_base64": "%%%這不是base64%%%"}
    not_an_image = {**BODY, "image_base64": base64.b64encode(b"hello").decode()}

    assert client.post("/v1/qa/ask-photo", json=not_base64).status_code == 400
    assert client.post("/v1/qa/ask-photo", json=not_an_image).status_code == 400


def test_a_photo_over_the_limit_is_413(client):
    big = base64.b64encode(b"\xff\xd8\xff\xe0" + b"\x00" * 5000).decode()

    assert client.post("/v1/qa/ask-photo", json={**BODY, "image_base64": big}).status_code == 413


def test_photo_questions_are_unavailable_when_photos_are_not_enabled(tmp_path, wav, persona, llm):
    with build_client(tmp_path, wav, persona, llm, photos=False) as client:
        body = {**BODY, "image_base64": JPEG_B64}
        assert client.post("/v1/qa/ask-photo", json=body).status_code == 503


def test_expired_photos_are_cleared_in_the_background_even_without_questions(
    tmp_path, wav, persona, llm
):
    import os

    photos = tmp_path / "photos"
    photos.mkdir()
    old = photos / "old.jpg"
    old.write_bytes(b"\xff\xd8\xff\xe0")
    os.utime(old, (1, 1))  # 1970 年：一定過期
    config = HostConfig(home=tmp_path)

    def factory(quota, journey):
        return QaService(
            llm,
            FakeNearby(),
            FakeSpeech(),
            persona_path=persona,
            out_dir=tmp_path / "qa",
            quota=quota,
            journey=journey,
            photos=PhotoStore(photos),
        )

    app = create_app(
        config, preparer=FakePreparer(wav), answerer_factory=factory, photo_purge_interval_s=0.01
    )
    with TestClient(app):
        for _ in range(100):
            if not old.exists():
                break
            time.sleep(0.02)

    assert not old.exists()


def test_the_request_limit_matches_the_photo_limit(client):
    # 8 MB 的照片 base64 後約 11.2M 字元：欄位上限不能比這個大太多，否則白白解碼
    from buddy_host.app import AskPhotoBody

    limit = AskPhotoBody.model_fields["image_base64"].metadata[0].max_length
    assert 8 * 1024 * 1024 * 4 // 3 <= limit <= 8 * 1024 * 1024 * 4 // 3 + 100_000


def test_an_answer_the_app_gave_up_on_can_be_cancelled(tmp_path, wav, persona):
    llm = FakeLlm(hold=asyncio.Event())  # 永遠不放行：模擬 Claude 還在寫
    with build_client(tmp_path, wav, persona, llm) as client:
        answer_id = client.post("/v1/qa/ask", json=BODY).json()["id"]

        response = client.post("/v1/qa/cancel", params={"id": answer_id})

        assert response.status_code == 200
        assert response.json() == {"cancelled": True}
        body = wait_for_answer(client, answer_id)
        assert (body["status"], body["reason"]) == ("failed", "cancelled")
        assert client.post("/v1/qa/cancel", params={"id": answer_id}).json() == {"cancelled": False}


def test_cancelling_an_unknown_answer_is_404_and_needs_the_token(tmp_path, wav, persona, llm):
    with build_client(tmp_path, wav, persona, llm) as client:
        assert client.post("/v1/qa/cancel", params={"id": "nope"}).status_code == 404
        del client.headers["X-Buddy-Token"]
        assert client.post("/v1/qa/cancel", params={"id": "x"}).status_code == 401


CONTRACT = Path(__file__).parents[3] / "contract"


def contract(name: str) -> dict:
    return json.loads((CONTRACT / f"{name}.json").read_text(encoding="utf-8"))


def stable(body: dict) -> dict:
    """答案 id 與延遲秒數每次不同，換成契約檔裡的固定值再比。"""
    body = dict(body)
    if "id" in body:
        body["id"] = "a1b2c3d4e5f6"
    if body.get("first_segment_seconds") is not None:
        body["first_segment_seconds"] = 0.5
    return body


def test_the_responses_match_the_contract_the_app_is_tested_against(tmp_path, wav, persona):
    hold = asyncio.Event()
    with build_client(tmp_path, wav, persona, FakeLlm()) as client:
        asked = client.post("/v1/qa/ask", json=BODY).json()
        done = wait_for_answer(client, asked["id"])
        assert stable(asked) == contract("qa-ask")
        assert stable(done) == contract("qa-answer-done")
    with build_client(tmp_path, wav, persona, FakeLlm(hold=hold)) as client:
        answer_id = client.post("/v1/qa/ask", json=BODY).json()["id"]
        cancelled = client.post("/v1/qa/cancel", params={"id": answer_id}).json()
        failed = wait_for_answer(client, answer_id)
        assert cancelled == contract("qa-cancel")
        assert stable(failed) == contract("qa-answer-failed")
