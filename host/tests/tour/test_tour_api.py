import json
import threading
import time
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from buddy_host.app import create_app
from buddy_host.config import HostConfig
from buddy_host.narration.preparer import PreparedNarration

BODY = {
    "lat": 25.056,
    "lon": 121.51,
    "heading_deg": 200,
    "mode": "walking",
    "companions": "family",
    "with_children": True,
    "local_time": "2026-10-20T15:04:00+08:00",
}


class FakePreparer:
    def __init__(self, wav):
        self.wav = wav
        self.calls = []

    async def prepare(self, location, *, exclude_ids=(), traveler=None, **_):
        self.calls.append((location, set(exclude_ids), traveler))
        return [
            PreparedNarration(
                "wiki:霞海城隍廟",
                "霞海城隍廟",
                "稿",
                self.wav,
                self.wav,
                34.7,
                50.0,
                25.0556,
                121.5103,
            )
        ]


@pytest.fixture
def wav(tmp_path):
    path = tmp_path / "a.wav"
    path.write_bytes(b"RIFF....WAVEdata")
    return path


@pytest.fixture
def preparer(wav):
    return FakePreparer(wav)


@pytest.fixture
def client(tmp_path, preparer):
    config = HostConfig(home=tmp_path, token="s3cret")
    with TestClient(create_app(config, preparer=preparer)) as client:
        client.headers["X-Buddy-Token"] = "s3cret"
        yield client


def wait_for(client, count, after=0):
    for _ in range(100):
        body = client.get("/v1/tour/narrations", params={"after": after}).json()
        if len(body["narrations"]) >= count:
            return body
        time.sleep(0.02)
    raise AssertionError(f"沒有等到 {count} 段介紹：{body}")


def test_tour_endpoints_require_the_token(tmp_path, preparer):
    config = HostConfig(home=tmp_path, token="s3cret")
    with TestClient(create_app(config, preparer=preparer)) as bare:
        assert bare.post("/v1/tour/start", json=BODY).status_code == 401
        assert bare.post("/v1/tour/location", json=BODY).status_code == 401
        assert bare.post("/v1/tour/end").status_code == 401
        assert bare.get("/v1/tour/narrations").status_code == 401
        assert bare.get("/v1/tour/audio", params={"id": "x"}).status_code == 401


def test_start_prepares_the_start_area_and_publishes_the_narration(client, preparer):
    assert client.post("/v1/tour/start", json=BODY).status_code == 200

    body = wait_for(client, 1)

    assert body["active"] is True
    assert body["narrations"] == [
        {
            "seq": 1,
            "id": "wiki:霞海城隍廟",
            "name": "霞海城隍廟",
            "lat": 25.0556,
            "lon": 121.5103,
            "audio_seconds": 34.7,
        }
    ]
    location, _, traveler = preparer.calls[0]
    assert (location.lat, location.lon, location.heading_deg) == (25.056, 121.51, 200)
    assert (traveler.mode, traveler.companions) == ("walking", "family")
    assert traveler.with_children is True
    assert traveler.local_time.hour == 15


def test_traveler_fields_are_optional(client, preparer):
    client.post("/v1/tour/start", json={"lat": 25.0, "lon": 121.5})
    wait_for(client, 1)

    _, _, traveler = preparer.calls[0]
    assert (traveler.mode, traveler.companions, traveler.local_time) == (None, None, None)
    assert traveler.with_children is False


def test_location_before_start_is_a_conflict(client):
    assert client.post("/v1/tour/location", json=BODY).status_code == 409


def test_location_report_after_start_is_accepted(client):
    client.post("/v1/tour/start", json=BODY)

    response = client.post("/v1/tour/location", json=BODY)

    assert response.status_code == 200


@pytest.mark.parametrize(
    "patch",
    [{"lat": 91}, {"lon": 181}, {"mode": "flying"}, {"companions": "crowd"}, {"heading_deg": 400}],
)
def test_invalid_reports_are_rejected(client, patch):
    assert client.post("/v1/tour/start", json={**BODY, **patch}).status_code == 422


def test_narrations_after_the_cursor_only(client):
    client.post("/v1/tour/start", json=BODY)
    wait_for(client, 1)

    assert client.get("/v1/tour/narrations", params={"after": 1}).json()["narrations"] == []


def test_audio_is_served_for_a_published_narration(client):
    client.post("/v1/tour/start", json=BODY)
    wait_for(client, 1)

    response = client.get("/v1/tour/audio", params={"id": "wiki:霞海城隍廟"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF....WAVEdata"


def test_audio_for_an_unknown_id_is_not_found(client):
    client.post("/v1/tour/start", json=BODY)

    assert client.get("/v1/tour/audio", params={"id": "../../etc/passwd"}).status_code == 404


def test_end_stops_the_tour_and_forgets_its_narrations(client):
    client.post("/v1/tour/start", json=BODY)
    wait_for(client, 1)

    assert client.post("/v1/tour/end").status_code == 200

    body = client.get("/v1/tour/narrations").json()
    assert body["active"] is False
    assert body["narrations"] == []


def test_stopped_reason_is_visible_to_the_app(tmp_path, wav):
    from buddy_host.llm.claude_cli import QuotaExceededError

    class Exhausted:
        async def prepare(self, *args, **kwargs):
            raise QuotaExceededError("You've hit your limit")

    config = HostConfig(home=tmp_path)
    with TestClient(create_app(config, preparer=Exhausted())) as client:
        client.post("/v1/tour/start", json=BODY)
        for _ in range(100):
            body = client.get("/v1/tour/narrations").json()
            if body["stopped_reason"]:
                break
            time.sleep(0.02)

    assert body["stopped_reason"] == "quota"


def test_tour_endpoints_are_unavailable_without_a_preparer(tmp_path):
    config = HostConfig(home=tmp_path)
    with TestClient(create_app(config)) as client:
        assert client.post("/v1/tour/start", json=BODY).status_code == 503


def usage_entry() -> dict:
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "purpose": "write",
        "model_requested": "sonnet",
        "modelUsage": {"claude-sonnet-5-5": {"inputTokens": 2, "outputTokens": 300}},
        "rate_limit_events": [
            {"status": "allowed", "unifiedWindows": {"five_hour": {"utilization": 0.3}}}
        ],
        "is_error": False,
        "error": None,
    }


def test_ending_a_tour_writes_a_usage_report_and_returns_its_summary(tmp_path, preparer):
    from buddy_host.llm.usage_log import UsageLog

    log_path = tmp_path / "usage.jsonl"
    reports = tmp_path / "reports"
    config = HostConfig(home=tmp_path)
    app = create_app(config, preparer=preparer, usage_log_path=log_path, reports_dir=reports)
    with TestClient(app) as client:
        client.post("/v1/tour/start", json=BODY)
        wait_for(client, 1)
        UsageLog(log_path).append(usage_entry())

        response = client.post("/v1/tour/end")

    summary = response.json()["summary"]
    assert summary["calls"] == 1
    assert summary["narrations"] == 1
    assert summary["hit_limit"] is False
    assert summary["utilization"]["five_hour"]["last"] == 0.3
    [report_file] = reports.glob("tour-*.json")
    assert len(json.loads(report_file.read_text(encoding="utf-8"))["calls"]) == 1


def test_ending_without_a_usage_log_still_summarizes_the_tour(client):
    client.post("/v1/tour/start", json=BODY)
    wait_for(client, 1)

    summary = client.post("/v1/tour/end").json()["summary"]

    assert summary["calls"] == 0
    assert summary["narrations"] == 1


def test_ending_a_tour_that_never_started_has_no_summary(client):
    body = client.post("/v1/tour/end").json()

    assert body == {"status": "ended", "summary": None}


def test_played_narrations_are_remembered_and_unknown_ones_are_ignored(tmp_path, preparer):
    config = HostConfig(home=tmp_path)
    app = create_app(config, preparer=preparer, journey_path=tmp_path / "journey.json")
    with TestClient(app) as client:
        client.post("/v1/tour/start", json=BODY)
        wait_for(client, 1)

        known = client.post("/v1/tour/played", json={"id": "wiki:霞海城隍廟"})
        unknown = client.post("/v1/tour/played", json={"id": "wiki:沒有這段"})
        again = client.post("/v1/tour/played", json={"id": "wiki:霞海城隍廟"})

    assert (known.status_code, unknown.status_code, again.status_code) == (200, 200, 200)
    saved = json.loads((tmp_path / "journey.json").read_text(encoding="utf-8"))
    assert list(saved["visited"]) == ["wiki:霞海城隍廟"]
    assert [stop["id"] for stop in saved["trip"]["stops"]] == ["wiki:霞海城隍廟"]


def test_start_says_whether_it_continued_the_previous_trip(tmp_path, preparer):
    config = HostConfig(home=tmp_path)
    app = create_app(config, preparer=preparer, journey_path=tmp_path / "journey.json")
    with TestClient(app) as client:
        first = client.post("/v1/tour/start", json=BODY).json()
        second = client.post("/v1/tour/start", json=BODY).json()  # 沒按結束就又出發
        client.post("/v1/tour/end")
        third = client.post("/v1/tour/start", json=BODY).json()

    assert first["resumed"] is False
    assert second["resumed"] is True
    assert third["resumed"] is False


def test_the_report_of_an_abandoned_trip_is_still_written(tmp_path, preparer):
    from buddy_host.tour.journey import JourneyMemory

    journey_path = tmp_path / "journey.json"
    old = JourneyMemory(journey_path)
    old.begin(1000.0)  # 很久以前出發、一直沒按結束
    old.touch(2000.0)
    config = HostConfig(home=tmp_path)
    reports = tmp_path / "reports"
    app = create_app(config, preparer=preparer, journey_path=journey_path, reports_dir=reports)
    with TestClient(app) as client:
        client.post("/v1/tour/start", json=BODY)

    [report_file] = reports.glob("tour-*.json")
    report = json.loads(report_file.read_text(encoding="utf-8"))
    assert report["started_at"].startswith("1970-01-01T00:16:40")


def test_writing_the_usage_report_does_not_block_the_event_loop(tmp_path, preparer, monkeypatch):
    """報告要讀整份 usage.jsonl，只會越來越大：不能在事件迴圈的執行緒上做。"""
    from buddy_host import app as app_module
    from buddy_host.tour.session import TourSession

    seen: dict[str, int] = {}
    real_end = TourSession.end

    def end(self):
        seen["loop"] = threading.get_ident()  # tour_end 在事件迴圈上呼叫它
        return real_end(self)

    def fake_finish(recap, usage_log_path, reports_dir, qa_latency_log_path=None):
        seen.setdefault("reports", []).append(threading.get_ident())
        return {"calls": 0}

    monkeypatch.setattr(TourSession, "end", end)
    monkeypatch.setattr(app_module, "finish_tour", fake_finish)
    config = HostConfig(home=tmp_path)
    with TestClient(create_app(config, preparer=preparer)) as client:
        client.post("/v1/tour/start", json=BODY)
        wait_for(client, 1)
        response = client.post("/v1/tour/end")

    assert response.json()["summary"] == {"calls": 0}
    assert seen["reports"] and seen["loop"] not in seen["reports"]


def test_the_report_of_an_abandoned_trip_is_not_written_on_the_event_loop_either(
    tmp_path, preparer, monkeypatch
):
    from buddy_host import app as app_module
    from buddy_host.tour.journey import JourneyMemory

    old = JourneyMemory(tmp_path / "journey.json")
    old.begin(1000.0)  # 很久以前出發、一直沒按結束
    seen: dict[str, list[int]] = {"reports": []}
    loop_threads: list[int] = []

    def fake_finish(recap, usage_log_path, reports_dir, qa_latency_log_path=None):
        seen["reports"].append(threading.get_ident())

    from buddy_host.tour.session import TourSession

    real_start = TourSession.start

    def start(self, fix):
        loop_threads.append(threading.get_ident())
        return real_start(self, fix)

    monkeypatch.setattr(TourSession, "start", start)
    monkeypatch.setattr(app_module, "finish_tour", fake_finish)
    config = HostConfig(home=tmp_path)
    app = create_app(config, preparer=preparer, journey_path=tmp_path / "journey.json")
    with TestClient(app) as client:
        client.post("/v1/tour/start", json=BODY)

    assert len(seen["reports"]) == 1
    assert loop_threads[0] not in seen["reports"]
