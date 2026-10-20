import pytest

from buddy_host.llm.budget import BudgetedLlm, LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import LlmRequest, LlmResult, Purpose


class FakeLlm:
    def __init__(self):
        self.calls = 0

    async def run(self, request, on_text=None):
        self.calls += 1
        return LlmResult("ok", "sonnet", {}, {}, {}, 1)


REQUEST = LlmRequest("hi", Purpose.WRITE)


async def test_calls_pass_through_until_the_budget_is_used_up():
    inner = FakeLlm()
    llm = BudgetedLlm(inner, max_calls=2)

    await llm.run(REQUEST)
    await llm.run(REQUEST)

    assert inner.calls == 2
    assert llm.calls_used == 2
    assert llm.calls_left == 0


async def test_the_call_over_the_budget_is_refused_without_reaching_claude():
    inner = FakeLlm()
    llm = BudgetedLlm(inner, max_calls=1)
    await llm.run(REQUEST)

    with pytest.raises(LlmBudgetExhaustedError):
        await llm.run(REQUEST)

    assert inner.calls == 1


def test_budget_exhaustion_is_a_quota_error_so_the_preparer_stops_everything():
    assert issubclass(LlmBudgetExhaustedError, QuotaExceededError)


async def test_a_failed_call_still_counts():
    class Boom(FakeLlm):
        async def run(self, request, on_text=None):
            raise RuntimeError("boom")

    llm = BudgetedLlm(Boom(), max_calls=3)

    with pytest.raises(RuntimeError):
        await llm.run(REQUEST)

    assert llm.calls_used == 1


def test_a_negative_budget_is_rejected():
    with pytest.raises(ValueError):
        BudgetedLlm(FakeLlm(), max_calls=-1)


async def test_tool_callback_is_forwarded_only_when_given():
    seen = []

    class ToolLlm(FakeLlm):
        async def run(self, request, on_text=None, on_tool=None):
            seen.append(on_tool)
            return await super().run(request, on_text)

    llm = BudgetedLlm(ToolLlm(), max_calls=3)
    callback = lambda name: None  # noqa: E731

    await llm.run(REQUEST, on_tool=callback)
    await llm.run(REQUEST)

    assert seen == [callback, None]


async def test_old_style_llms_without_on_tool_still_work_when_no_callback_is_given():
    await BudgetedLlm(FakeLlm(), max_calls=1).run(REQUEST)
