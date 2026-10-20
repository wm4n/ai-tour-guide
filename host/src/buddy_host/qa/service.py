"""問答：App 送來一個問題，這裡請 Claude 回答，App 以 id 輪詢答案與狀態。

- 每個問題都是新的一次 Claude 呼叫（旅程上下文由這裡組進 prompt）。
- 額度與旅程準備共用同一個 `QuotaGate`：任一邊撞到上限兩邊一起停，恢復後下一次呼叫即探測。
- 答案存在記憶體裡，只留最近幾筆；App 輪詢拿到結果就用完了。
"""

import asyncio
import logging
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import ForbiddenModelError, LlmRequest, LlmResult
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.prompt import WEB_TOOLS, ScriptContext, load_persona
from buddy_host.places.models import Location
from buddy_host.qa.prompt import AskContext, build_answer_request
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import TourFix

logger = logging.getLogger(__name__)

NEARBY_LIMIT = 5
NEARBY_TIMEOUT_S = 10.0  # 附近景點只是輔助：查不到就空手回答，不拖慢答案
KEPT_ANSWERS = 50


class LlmLike(Protocol):
    async def run(self, request: LlmRequest, on_text=None, on_tool=None) -> LlmResult: ...


class NearbyLike(Protocol):
    async def nearby(self, location: Location, *, limit: int = ...) -> list[ScriptContext]: ...


@dataclass
class Answer:
    id: str
    status: Literal["answering", "done", "failed"] = "answering"
    text: str = ""
    searching_web: bool = False  # Claude 動用了上網工具：App 可以說「我上網查一下」
    reason: str | None = None  # failed 時：quota／llm_budget／forbidden_model／error


class QaService:
    def __init__(
        self,
        llm: LlmLike,
        nearby: NearbyLike,
        *,
        persona_path: Path,
        quota: QuotaGate,
        journey: JourneyMemory,
        nearby_limit: int = NEARBY_LIMIT,
        nearby_timeout_s: float = NEARBY_TIMEOUT_S,
        keep: int = KEPT_ANSWERS,
    ):
        self._llm = llm
        self._nearby = nearby
        self._persona_path = persona_path
        self._quota = quota
        self._journey = journey
        self._nearby_limit = nearby_limit
        self._nearby_timeout_s = nearby_timeout_s
        self._keep = keep
        self._answers: OrderedDict[str, Answer] = OrderedDict()
        self._tasks: set[asyncio.Task] = set()

    def ask(self, question: str, fix: TourFix, *, more: bool = False) -> str:
        """收下問題、開始回答，回傳答案的 id（App 用它輪詢）。需要在事件迴圈裡呼叫。"""
        answer = Answer(uuid.uuid4().hex[:12])
        self._answers[answer.id] = answer
        while len(self._answers) > self._keep:
            self._answers.popitem(last=False)
        task = asyncio.create_task(self._answer(answer, question.strip(), fix, more))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return answer.id

    def answer(self, answer_id: str) -> Answer | None:
        return self._answers.get(answer_id)

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.wait(set(self._tasks))

    async def _answer(self, answer: Answer, question: str, fix: TourFix, more: bool) -> None:
        if not self._quota.admit():  # 額度還沒恢復：連 Claude 都不呼叫
            return self._fail(answer, "quota")
        try:
            context = await self._context(question, fix, more)
            request = build_answer_request(load_persona(self._persona_path), context)
            result = await self._llm.run(request, on_tool=lambda tool: self._on_tool(answer, tool))
        except LlmBudgetExhaustedError:  # 先於 QuotaExceededError：它是子類別，但永遠不會自己恢復
            return self._fail(answer, "llm_budget")
        except QuotaExceededError as error:
            self._quota.trip(error.resets_at)
            return self._fail(answer, "quota")
        except ForbiddenModelError:
            return self._fail(answer, "forbidden_model")
        except Exception:
            logger.exception("回答問題失敗")
            return self._fail(answer, "error")
        text = result.text.strip()
        if not text:
            logger.warning("Claude 回了空的答案")
            return self._fail(answer, "error")
        answer.text = text
        answer.status = "done"

    async def _context(self, question: str, fix: TourFix, more: bool) -> AskContext:
        try:
            nearby = await asyncio.wait_for(
                self._nearby.nearby(fix.location, limit=self._nearby_limit),
                self._nearby_timeout_s,
            )
        except Exception:  # 含逾時：沒有附近資料也要能回答（Claude 可以自己上網）
            logger.exception("查附近景點失敗，不帶附近資料回答")
            nearby = []
        return AskContext(
            question=question,
            location=fix.location,
            traveler=fix.traveler,
            nearby=tuple(nearby),
            recent_topics=self._journey.recent_topics(),
            told_before=self._journey.told_before(),
            last_told=self._journey.last_told(),
            more=more,
        )

    @staticmethod
    def _on_tool(answer: Answer, tool: str) -> None:
        if tool in WEB_TOOLS:
            answer.searching_web = True

    @staticmethod
    def _fail(answer: Answer, reason: str) -> None:
        answer.status = "failed"
        answer.reason = reason
