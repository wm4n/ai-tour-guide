"""問答：App 送來一個問題，這裡請 Claude 回答、合成語音，App 以 id 輪詢並逐段下載。

- 每個問題都是新的一次 Claude 呼叫（旅程上下文由這裡組進 prompt）。
- 答案不等寫完：串流的文字一寫完一句就切段、交給語音管線（合成＋Whisper 驗收＋換 seed／
  拆句／跳過，規則全在 `SpeechPipeline`），做好一段就可以下載一段。第一段盡量短。
- 額度與旅程準備共用同一個 `QuotaGate`：任一邊撞到上限兩邊一起停，恢復後下一次呼叫即探測。
- 「收到問題 → 第一段可下載」的秒數記進 latency log，用量報告取平均。
- 答案存在記憶體裡、音檔放在 out_dir/<id>/，都只留最近幾筆。
"""

import asyncio
import logging
import shutil
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from buddy_host.llm.budget import LlmBudgetExhaustedError
from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import ForbiddenModelError, LlmRequest, LlmResult
from buddy_host.llm.quota import QuotaGate
from buddy_host.llm.usage_log import UsageLog
from buddy_host.narration.prompt import WEB_TOOLS, ScriptContext, load_persona
from buddy_host.places.models import Location
from buddy_host.qa.prompt import AskContext, build_answer_request
from buddy_host.qa.segmenter import AnswerSegmenter
from buddy_host.speech.pipeline import SpeechResult
from buddy_host.speech.pipeline import write_outputs as write_speech
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


class SpeechLike(Protocol):
    def run(self, text: str) -> SpeechResult: ...


@dataclass
class AnswerSegment:
    index: int  # 連續編號：驗收不過被跳過的段落不佔編號
    audio_seconds: float


@dataclass
class Answer:
    id: str
    status: Literal["answering", "done", "failed"] = "answering"  # done＝文字寫完、每段都做完
    text: str = ""  # Claude 的完整答案；寫完才有
    segments: list[AnswerSegment] = field(default_factory=list)  # 已經可以下載的段落，依序
    first_segment_seconds: float | None = None  # 收到問題 → 第一段可下載
    searching_web: bool = False  # Claude 動用了上網工具：App 可以說「我上網查一下」
    # failed 時：quota／llm_budget／forbidden_model／no_audio／error
    reason: str | None = None


class QaService:
    def __init__(
        self,
        llm: LlmLike,
        nearby: NearbyLike,
        speech: SpeechLike,
        *,
        persona_path: Path,
        out_dir: Path,
        quota: QuotaGate,
        journey: JourneyMemory,
        latency_log: UsageLog | None = None,
        monotonic=time.monotonic,
        nearby_limit: int = NEARBY_LIMIT,
        nearby_timeout_s: float = NEARBY_TIMEOUT_S,
        keep: int = KEPT_ANSWERS,
    ):
        self._llm = llm
        self._nearby = nearby
        self._speech = speech
        self._persona_path = persona_path
        self._out_dir = out_dir
        self._quota = quota
        self._journey = journey
        self._latency_log = latency_log
        self._monotonic = monotonic
        self._nearby_limit = nearby_limit
        self._nearby_timeout_s = nearby_timeout_s
        self._keep = keep
        self._answers: OrderedDict[str, Answer] = OrderedDict()
        self._tasks: set[asyncio.Task] = set()

    def ask(self, question: str, fix: TourFix, *, more: bool = False) -> str:
        """收下問題、開始回答，回傳答案的 id（App 用它輪詢）。需要在事件迴圈裡呼叫。"""
        started = self._monotonic()
        answer = Answer(uuid.uuid4().hex[:12])
        self._answers[answer.id] = answer
        while len(self._answers) > self._keep:
            evicted, _ = self._answers.popitem(last=False)
            shutil.rmtree(self._out_dir / evicted, ignore_errors=True)
        task = asyncio.create_task(self._answer(answer, question.strip(), fix, more, started))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return answer.id

    def answer(self, answer_id: str) -> Answer | None:
        return self._answers.get(answer_id)

    def audio_path(self, answer_id: str, index: int) -> Path | None:
        answer = self._answers.get(answer_id)
        if answer is None or not any(s.index == index for s in answer.segments):
            return None
        return self._segment_path(answer_id, index)

    async def wait_idle(self) -> None:
        while self._tasks:
            await asyncio.wait(set(self._tasks))

    def _segment_path(self, answer_id: str, index: int) -> Path:
        return self._out_dir / answer_id / f"seg-{index}.wav"

    async def _answer(
        self, answer: Answer, question: str, fix: TourFix, more: bool, started: float
    ) -> None:
        if not self._quota.admit():  # 額度還沒恢復：連 Claude 都不呼叫
            return self._fail(answer, "quota")
        segments: asyncio.Queue[str | None] = asyncio.Queue()
        speaker = asyncio.create_task(self._speak(answer, segments, started))
        try:
            text = await self._write(answer, question, fix, more, segments)
        except LlmBudgetExhaustedError:  # 先於 QuotaExceededError：它是子類別，但永遠不會自己恢復
            reason = "llm_budget"
        except QuotaExceededError as error:
            self._quota.trip(error.resets_at)
            reason = "quota"
        except ForbiddenModelError:
            reason = "forbidden_model"
        except Exception:
            logger.exception("回答問題失敗")
            reason = "error"
        else:
            reason = None
        if reason is not None:
            speaker.cancel()  # 已經做好的段落留著，還沒做的不做了
            await asyncio.gather(speaker, return_exceptions=True)
            return self._fail(answer, reason)

        answer.text = text
        segments.put_nowait(None)
        await speaker
        if not answer.segments:  # 每一段都驗收不過：寧可少講，但整個答案沒聲音就是失敗
            return self._fail(answer, "no_audio")
        answer.status = "done"

    async def _write(
        self,
        answer: Answer,
        question: str,
        fix: TourFix,
        more: bool,
        segments: "asyncio.Queue[str | None]",
    ) -> str:
        """請 Claude 回答；寫到哪切到哪，一段一段交給合成。回傳完整答案。"""
        segmenter = AnswerSegmenter()
        queued = 0

        def enqueue(texts: list[str]) -> None:
            nonlocal queued
            for text in texts:
                segments.put_nowait(text)
                queued += 1

        def on_tool(tool: str) -> None:
            if tool in WEB_TOOLS:
                answer.searching_web = True
                segmenter.discard()  # 查資料之前說的開場白不念

        context = await self._context(question, fix, more)
        request = build_answer_request(load_persona(self._persona_path), context)
        result = await self._llm.run(
            request, on_text=lambda delta: enqueue(segmenter.feed(delta)), on_tool=on_tool
        )
        text = result.text.strip()
        if not text:
            raise ValueError("Claude 回了空的答案")
        tail = segmenter.finish()
        if not queued and not tail:  # 沒有串流（或串流的文字全被丟掉）：改用最終的答案
            tail = segmenter.feed(text) + segmenter.finish()
        enqueue(tail)
        return text

    async def _speak(
        self, answer: Answer, segments: "asyncio.Queue[str | None]", started: float
    ) -> None:
        """一次合成一段（只有一顆 GPU）；做好就加進 answer.segments，App 即可下載。"""
        while (text := await segments.get()) is not None:
            index = len(answer.segments)
            try:
                seconds = await asyncio.to_thread(self._synthesize, answer.id, index, text)
            except Exception:  # 一段合成失敗只跳過這段
                logger.exception("答案語音合成失敗，跳過這一段：%s", text)
                continue
            if seconds <= 0:
                logger.warning("答案這一段驗收不過，跳過：%s", text)
                continue
            answer.segments.append(AnswerSegment(index, seconds))
            if index == 0:
                self._record_latency(answer, self._monotonic() - started)

    def _synthesize(self, answer_id: str, index: int, text: str) -> float:
        result = self._speech.run(text)
        if result.audio_seconds <= 0:
            return 0.0
        path = self._segment_path(answer_id, index)
        write_speech(result, path.parent, path.stem)
        return round(result.audio_seconds, 2)

    def _record_latency(self, answer: Answer, seconds: float) -> None:
        answer.first_segment_seconds = round(seconds, 2)
        if self._latency_log is None:
            return
        try:
            self._latency_log.append(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "answer_id": answer.id,
                    "first_segment_seconds": answer.first_segment_seconds,
                }
            )
        except OSError:
            logger.exception("問答延遲記錄寫入失敗")

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
    def _fail(answer: Answer, reason: str) -> None:
        answer.status = "failed"
        answer.reason = reason
