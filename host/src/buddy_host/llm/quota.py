"""從 `rate_limit_event` 與錯誤文字判斷「額度用完」，以及何時恢復（設計文件第 11 節）。"""

import time
from collections.abc import Callable


def _rejected(rate_limits: list[dict]) -> list[dict]:
    return [event for event in rate_limits if event.get("status") == "rejected"]


def quota_hit(rate_limits: list[dict], error: str | None) -> bool:
    return bool(_rejected(rate_limits)) or "hit your" in (error or "").lower()


def reset_time(rate_limits: list[dict]) -> float | None:
    """額度恢復的時間（epoch 秒）；只有錯誤文字、沒有被拒絕的事件時是 None。"""
    rejected = _rejected(rate_limits)
    value = rejected[-1].get("resetsAt") if rejected else None
    return float(value) if isinstance(value, int | float) else None


class QuotaGate:
    """額度用完後的共用閘門：旅程準備與問答都經過它，任一邊撞到上限，兩邊一起停。

    恢復不另外探測：到了恢復時間，下一次要呼叫 Claude 的人（`admit()`）就是探測；
    還是被拒絕就再 `trip()`，成功就繼續。
    """

    def __init__(
        self,
        *,
        retry_after_s: float = 900.0,  # 不知道額度何時恢復時，隔這麼久再試一次
        wall_clock: Callable[[], float] = time.time,  # resetsAt 是牆鐘時間
    ):
        self._retry_after_s = retry_after_s
        self._wall_clock = wall_clock
        self._resumes_at: float | None = None

    @property
    def tripped(self) -> bool:
        return self._resumes_at is not None

    def trip(self, resets_at: float | None = None) -> None:
        now = self._wall_clock()
        # 沒給或已過期的恢復時間不可信：否則每次呼叫都會重試一次
        known = resets_at is not None and resets_at > now
        self._resumes_at = resets_at if known else now + self._retry_after_s

    def blocked(self) -> bool:
        return self._resumes_at is not None and self._wall_clock() < self._resumes_at

    def may_probe(self) -> bool:
        return self._resumes_at is not None and self._wall_clock() >= self._resumes_at

    def admit(self) -> bool:
        """要呼叫 Claude 前問一聲：可以就回 True；到了恢復時間時順便解除閘門（這次呼叫即探測）。"""
        if self.blocked():
            return False
        self._resumes_at = None
        return True
