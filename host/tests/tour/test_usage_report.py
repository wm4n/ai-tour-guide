import json
from datetime import UTC, datetime

from buddy_host.llm.usage_log import UsageLog
from buddy_host.tour.session import TourRecap
from buddy_host.tour.usage_report import build_report, finish_tour, summarize, write_report

START = datetime(2026, 10, 20, 7, 0, tzinfo=UTC)
END = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)
RECAP = TourRecap(START.timestamp(), END.timestamp(), narrations=3, stopped_reason=None)


def at(minute: int) -> str:
    return datetime(2026, 10, 20, 7, minute, tzinfo=UTC).isoformat()


def event(five_hour: float, seven_day: float, status: str = "allowed") -> dict:
    return {
        "status": status,
        "unifiedWindows": {
            "five_hour": {"utilization": five_hour, "resetsAt": 1792440000},
            "seven_day": {"utilization": seven_day, "resetsAt": 1792652400},
        },
    }


def entry(minute: int, *, purpose="write", model="claude-sonnet-5-5", events=None, **extra) -> dict:
    return {
        "timestamp": at(minute),
        "purpose": purpose,
        "model_requested": "sonnet",
        "modelUsage": {
            model: {
                "inputTokens": 2,
                "outputTokens": 300,
                "cacheReadInputTokens": 17000,
                "cacheCreationInputTokens": 9800,
                "costUSD": 0.04,
            }
        },
        "rate_limit_events": events if events is not None else [event(0.26, 0.45)],
        "duration_ms": 5000,
        "is_error": False,
        "error": None,
        **extra,
    }


def test_each_call_is_listed_with_purpose_model_time_usage_and_utilization():
    report = build_report([entry(5, purpose="judge", model="claude-haiku-5-5")], RECAP)

    [call] = report["calls"]
    assert call["timestamp"] == at(5)
    assert call["purpose"] == "judge"
    assert call["model"] == "claude-haiku-5-5"
    assert call["tokens"] == {
        "input": 2,
        "output": 300,
        "cache_read": 17000,
        "cache_creation": 9800,
    }
    assert call["utilization"] == {"five_hour": 0.26, "seven_day": 0.45}
    assert call["hit_limit"] is False


def test_only_calls_made_during_the_tour_are_counted():
    early = entry(0)
    early["timestamp"] = datetime(2026, 10, 20, 6, 59, tzinfo=UTC).isoformat()
    late = entry(0)
    late["timestamp"] = datetime(2026, 10, 20, 8, 1, tzinfo=UTC).isoformat()

    report = build_report([early, entry(10), late], RECAP)

    assert [c["timestamp"] for c in report["calls"]] == [at(10)]


def test_utilization_change_is_the_difference_between_the_first_and_last_call():
    entries = [
        entry(5, events=[event(0.26, 0.45)]),
        entry(20, events=[event(0.31, 0.46)]),
        entry(40, events=[event(0.38, 0.47)]),
    ]

    report = build_report(entries, RECAP)

    five = report["totals"]["utilization"]["five_hour"]
    assert five == {"first": 0.26, "last": 0.38, "change": 0.12}
    assert report["totals"]["utilization"]["seven_day"]["change"] == 0.02


def test_hitting_the_limit_is_flagged_for_the_call_and_the_tour():
    rejected = entry(
        30,
        events=[event(1.0, 0.5, status="rejected")],
        is_error=True,
        error="You've hit your session limit",
        modelUsage={},
    )

    report = build_report([entry(5), rejected], RECAP)

    assert [c["hit_limit"] for c in report["calls"]] == [False, True]
    assert report["totals"]["hit_limit"] is True
    assert report["calls"][1]["model"] == "sonnet"  # 沒有 modelUsage 時退回請求的模型


def test_the_limit_hit_is_recognised_from_the_error_text_alone():
    text_only = entry(30, is_error=True, error="You've hit your weekly limit", modelUsage={})

    assert build_report([text_only], RECAP)["totals"]["hit_limit"] is True


def test_totals_count_calls_and_tokens_per_model():
    entries = [
        entry(5),
        entry(10),
        entry(15, purpose="judge", model="claude-haiku-5-5"),
    ]

    totals = build_report(entries, RECAP)["totals"]

    assert totals["calls"] == 3
    assert totals["by_model"]["claude-sonnet-5-5"] == {
        "calls": 2,
        "input": 4,
        "output": 600,
        "cache_read": 34000,
        "cache_creation": 19600,
    }
    assert totals["by_model"]["claude-haiku-5-5"]["calls"] == 1


def test_a_tour_without_calls_still_makes_a_report():
    report = build_report([], TourRecap(START.timestamp(), END.timestamp(), 2, "llm_budget"))

    assert report["calls"] == []
    assert report["totals"] == {"calls": 0, "hit_limit": False, "by_model": {}, "utilization": {}}
    assert report["narrations"] == 2
    assert report["stopped_reason"] == "llm_budget"
    assert report["duration_seconds"] == 3600


def test_the_summary_is_what_the_app_shows_at_the_end_of_a_tour():
    report = build_report(
        [entry(5, events=[event(0.26, 0.45)]), entry(20, events=[event(0.3, 0.45)])], RECAP
    )

    assert summarize(report) == {
        "calls": 2,
        "narrations": 3,
        "duration_seconds": 3600,
        "hit_limit": False,
        "utilization": {
            "five_hour": {"last": 0.3, "change": 0.04},
            "seven_day": {"last": 0.45, "change": 0.0},
        },
    }


def test_the_report_is_written_as_a_json_file_named_after_the_start(tmp_path):
    report = build_report([entry(5)], RECAP)

    path = write_report(report, tmp_path / "reports")

    assert path.name == "tour-20261020T070000Z.json"
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_a_call_that_used_two_models_is_counted_under_each():
    two = entry(5)
    two["modelUsage"]["claude-haiku-5-5"] = {"inputTokens": 1, "outputTokens": 10}

    report = build_report([two], RECAP)

    assert report["calls"][0]["tokens"]["output"] == 310
    by_model = report["totals"]["by_model"]
    assert by_model["claude-sonnet-5-5"]["output"] == 300
    assert by_model["claude-haiku-5-5"]["output"] == 10


def test_finish_tour_writes_the_report_and_returns_the_summary(tmp_path):
    log = tmp_path / "usage.jsonl"
    UsageLog(log).append(entry(5))

    summary = finish_tour(RECAP, log, tmp_path / "reports")

    assert summary["calls"] == 1
    assert len(list((tmp_path / "reports").glob("tour-*.json"))) == 1


def test_finish_tour_without_a_log_or_reports_dir_still_summarizes():
    summary = finish_tour(RECAP, None, None)

    assert summary["calls"] == 0
    assert summary["narrations"] == 3


def test_a_broken_usage_log_never_blocks_the_end_of_a_tour(tmp_path):
    log = tmp_path / "usage.jsonl"
    log.write_text("{not json\n", encoding="utf-8")

    assert finish_tour(RECAP, log, tmp_path / "reports") is None
