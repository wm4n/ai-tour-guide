"""Claude 呼叫次數的硬上限：每次呼叫都消耗 Claude Pro 額度，服務不能無上限地替前方準備稿子。"""

from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import LlmRequest, LlmResult


class LlmBudgetExhaustedError(QuotaExceededError):
    """繼承額度錯誤：AreaPreparer 看到它就會整批停下，而不是當成單段失敗略過。"""


class BudgetedLlm:
    def __init__(self, inner, *, max_calls: int):
        if max_calls < 0:
            raise ValueError("max_calls 不可為負數")
        self._inner = inner
        self._max_calls = max_calls
        self.calls_used = 0

    @property
    def calls_left(self) -> int:
        return self._max_calls - self.calls_used

    async def run(self, request: LlmRequest, on_text=None) -> LlmResult:
        if self.calls_used >= self._max_calls:
            raise LlmBudgetExhaustedError(f"已達 Claude 呼叫上限 {self._max_calls} 次")
        self.calls_used += 1  # 先記帳：呼叫失敗或逾時也可能已經消耗額度
        return await self._inner.run(request, on_text)
