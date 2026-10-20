"""一趟結束時的用量報告（設計文件第 11 節）：這一趟呼叫了 Claude 幾次、用了多少、額度變化多少。

資料來源是 `usage.jsonl`（每次呼叫一行），不另外記帳；本趟範圍用開始與結束的時間篩選。
`utilization` 取每次呼叫最後一個 `rate_limit_event` 的 `unifiedWindows`（5 小時與 7 天視窗），
「變化」是本趟第一次與最後一次呼叫之後的差，所以不含第一次呼叫本身的消耗。
`timestamp` 是呼叫完成的時間；結束時還在跑的呼叫會被取消，不會出現在報告裡。
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from buddy_host.llm.quota import quota_hit
from buddy_host.llm.usage_log import UsageLog
from buddy_host.tour.session import TourRecap

logger = logging.getLogger(__name__)

_TOKEN_FIELDS = {
    "input": "inputTokens",
    "output": "outputTokens",
    "cache_read": "cacheReadInputTokens",
    "cache_creation": "cacheCreationInputTokens",
}


def build_report(entries: list[dict], recap: TourRecap) -> dict:
    calls = [
        _summarize_call(entry)
        for entry in entries
        if recap.started_at
        <= datetime.fromisoformat(entry["timestamp"]).timestamp()
        <= recap.ended_at
    ]
    return {
        "started_at": _iso(recap.started_at),
        "ended_at": _iso(recap.ended_at),
        "duration_seconds": round(recap.ended_at - recap.started_at),
        "narrations": recap.narrations,
        "stopped_reason": recap.stopped_reason,
        "calls": calls,
        "totals": _totals(calls),
    }


def finish_tour(
    recap: TourRecap, usage_log_path: Path | None, reports_dir: Path | None
) -> dict | None:
    """寫出本趟的用量報告並回傳 App 要顯示的摘要。

    報告只是附帶的：任何一步失敗都只記 log、回傳 None，不能讓「結束」本身失敗。
    """
    try:
        entries = UsageLog(usage_log_path).read_all() if usage_log_path else []
        report = build_report(entries, recap)
        if reports_dir is not None:
            write_report(report, reports_dir)
        return summarize(report)
    except Exception:
        logger.exception("產生用量報告失敗")
        return None


def summarize(report: dict) -> dict:
    """App 結束畫面顯示的摘要。"""
    totals = report["totals"]
    return {
        "calls": totals["calls"],
        "narrations": report["narrations"],
        "duration_seconds": report["duration_seconds"],
        "hit_limit": totals["hit_limit"],
        "utilization": {
            window: {"last": value["last"], "change": value["change"]}
            for window, value in totals["utilization"].items()
        },
    }


def write_report(report: dict, reports_dir: Path) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.fromisoformat(report["started_at"]).strftime("%Y%m%dT%H%M%SZ")
    path = reports_dir / f"tour-{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, UTC).isoformat()


def _summarize_call(entry: dict) -> dict:
    events = entry.get("rate_limit_events") or []
    # 沒有 modelUsage（呼叫失敗）時，用量記在請求的模型名下
    models = {
        name: {key: usage.get(field, 0) for key, field in _TOKEN_FIELDS.items()}
        for name, usage in (entry.get("modelUsage") or {}).items()
    } or {entry.get("model_requested"): dict.fromkeys(_TOKEN_FIELDS, 0)}
    return {
        "timestamp": entry["timestamp"],
        "purpose": entry.get("purpose"),
        "model": next(iter(models)),
        "models": models,
        "tokens": {key: sum(m[key] for m in models.values()) for key in _TOKEN_FIELDS},
        "duration_ms": entry.get("duration_ms"),
        "utilization": _utilization(events),
        "hit_limit": quota_hit(events, entry.get("error")),
        "error": entry.get("error"),
    }


def _utilization(events: list[dict]) -> dict[str, float]:
    latest: dict[str, float] = {}
    for event in events:
        for window, value in (event.get("unifiedWindows") or {}).items():
            if "utilization" in value:
                latest[window] = value["utilization"]
    return latest


def _totals(calls: list[dict]) -> dict:
    by_model: dict[str, dict[str, int]] = {}
    for call in calls:
        for name, tokens in call["models"].items():
            total = by_model.setdefault(name, {"calls": 0, **dict.fromkeys(_TOKEN_FIELDS, 0)})
            total["calls"] += 1
            for key, value in tokens.items():
                total[key] += value
    return {
        "calls": len(calls),
        "hit_limit": any(call["hit_limit"] for call in calls),
        "by_model": by_model,
        "utilization": _utilization_changes(calls),
    }


def _utilization_changes(calls: list[dict]) -> dict[str, dict[str, float]]:
    changes: dict[str, dict[str, float]] = {}
    for call in calls:
        for window, value in call["utilization"].items():
            span = changes.setdefault(window, {"first": value, "last": value, "change": 0.0})
            span["last"] = value
            span["change"] = round(value - span["first"], 4)
    return changes
