"""從 `rate_limit_event` 與錯誤文字判斷「額度用完」，以及何時恢復（設計文件第 11 節）。"""


def _rejected(rate_limits: list[dict]) -> list[dict]:
    return [event for event in rate_limits if event.get("status") == "rejected"]


def quota_hit(rate_limits: list[dict], error: str | None) -> bool:
    return bool(_rejected(rate_limits)) or "hit your" in (error or "").lower()


def reset_time(rate_limits: list[dict]) -> float | None:
    """額度恢復的時間（epoch 秒）；只有錯誤文字、沒有被拒絕的事件時是 None。"""
    rejected = _rejected(rate_limits)
    value = rejected[-1].get("resetsAt") if rejected else None
    return float(value) if isinstance(value, int | float) else None
