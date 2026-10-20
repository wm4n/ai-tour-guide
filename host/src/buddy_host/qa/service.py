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
from buddy_host.qa.photos import PhotoStore
from buddy_host.qa.prompt import AskContext, PhotoInput, build_answer_request
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


class AnswerTurnLike(Protocol):
    def run(self, text: str) -> SpeechResult: ...
    def end(self) -> None: ...


class AnswerSpeechLike(Protocol):
    def begin(self) -> AnswerTurnLike:
        """開始一個問答的語音排程（整個答案持有一個位置，見 speech.scheduler）。"""
        ...


class PhotosUnavailable(RuntimeError):
    """主機沒有開放拍照提問（沒有照片存放處）。"""


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
        speech: AnswerSpeechLike,
        *,
        persona_path: Path,
        out_dir: Path,
        quota: QuotaGate,
        journey: JourneyMemory,
        latency_log: UsageLog | None = None,
        photos: PhotoStore | None = None,
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
        self._photos = photos
        self._monotonic = monotonic
        self._nearby_limit = nearby_limit
        self._nearby_timeout_s = nearby_timeout_s
        self._keep = keep
        self._answers: OrderedDict[str, Answer] = OrderedDict()
        self._tasks: set[asyncio.Task] = set()

    @property
    def photos_enabled(self) -> bool:
        return self._photos is not None

    def purge_photos(self) -> int:
        """刪掉超過保留期限的照片；回傳刪了幾張（沒有照片存放處時是 0）。"""
        return self._photos.purge() if self._photos is not None else 0

    def ask(self, question: str, fix: TourFix, *, more: bool = False) -> str:
        """收下問題、開始回答，回傳答案的 id（App 用它輪詢）。需要在事件迴圈裡呼叫。"""
        return self._start(question, fix, more=more, photo=None)

    async def ask_photo(self, question: str, fix: TourFix, image: bytes) -> str:
        """拍照提問：照片存在主機本機（有保留期限），Claude 用 Read 工具看。

        `fix.location.heading_deg` 是拍照時手機的指南針方向。不是照片（或太大）時丟 PhotoRejected，
        什麼都不會開始。
        """
        if self._photos is None:
            raise PhotosUnavailable("沒有照片存放處")
        path = await asyncio.to_thread(self._photos.save, image)  # 最大 8 MB 的寫檔，不卡事件迴圈
        return self._start(
            question, fix, more=False, photo=PhotoInput(path, fix.location.heading_deg)
        )

    def _start(self, question: str, fix: TourFix, *, more: bool, photo: PhotoInput | None) -> str:
        self.purge_photos()  # 每次發問順便清一次
        started = self._monotonic()
        answer = Answer(uuid.uuid4().hex[:12])
        self._answers[answer.id] = answer
        while len(self._answers) > self._keep:
            evicted, _ = self._answers.popitem(last=False)
            shutil.rmtree(self._out_dir / evicted, ignore_errors=True)
        task = asyncio.create_task(
            self._answer(answer, question.strip(), fix, more, started, photo)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return answer.id

    def clear_stored_audio(self) -> None:
        """清掉磁碟上所有答案的音檔。答案只存在記憶體裡，主機重啟後舊的目錄沒有人認領。"""
        shutil.rmtree(self._out_dir, ignore_errors=True)

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
        self,
        answer: Answer,
        question: str,
        fix: TourFix,
        more: bool,
        started: float,
        photo: PhotoInput | None,
    ) -> None:
        if not self._quota.admit():  # 額度還沒恢復：連 Claude 都不呼叫
            return self._fail(answer, "quota")
        segments: asyncio.Queue[str | None] = asyncio.Queue()
        turn = self._speech.begin()  # 從開始回答起就算問答優先，介紹不會趁 Claude 寫字的空檔插進來
        speaker = asyncio.create_task(self._speak(answer, segments, started, turn))
        try:
            reason = await self._converse(answer, question, fix, more, photo, segments, speaker)
        finally:
            # 不論成功、失敗或被取消都收掉合成的任務：已經做好的段落留著，還沒做的不做了
            speaker.cancel()
            await asyncio.gather(speaker, return_exceptions=True)
            turn.end()  # 還有一段在合成時，排程器會等它做完才讓出 GPU
        if reason is None:
            answer.status = "done"
        else:
            self._fail(answer, reason)

    async def _converse(
        self,
        answer: Answer,
        question: str,
        fix: TourFix,
        more: bool,
        photo: PhotoInput | None,
        segments: asyncio.Queue[str | None],
        speaker: asyncio.Task,
    ) -> str | None:
        """問 Claude、等每一段做完；回傳失敗原因，成功是 None。"""
        try:
            answer.text = await self._write(answer, question, fix, more, photo, segments)
        except LlmBudgetExhaustedError:  # 先於 QuotaExceededError：它是子類別，但永遠不會自己恢復
            return "llm_budget"
        except QuotaExceededError as error:
            self._quota.trip(error.resets_at)
            return "quota"
        except ForbiddenModelError:
            return "forbidden_model"
        except Exception:
            logger.exception("回答問題失敗")
            return "error"
        segments.put_nowait(None)
        try:
            await speaker
        except Exception:
            logger.exception("答案語音合成出了意外")
            return "error"
        # 每一段都驗收不過：寧可少講，但整個答案沒聲音就是失敗
        return None if answer.segments else "no_audio"

    async def _write(
        self,
        answer: Answer,
        question: str,
        fix: TourFix,
        more: bool,
        photo: PhotoInput | None,
        segments: asyncio.Queue[str | None],
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

        context = await self._context(question, fix, more, photo)
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
        self,
        answer: Answer,
        segments: asyncio.Queue[str | None],
        started: float,
        turn: AnswerTurnLike,
    ) -> None:
        """一次合成一段（只有一顆 GPU）；做好就加進 answer.segments，App 即可下載。"""
        while (text := await segments.get()) is not None:
            index = len(answer.segments)
            try:
                seconds = await asyncio.to_thread(self._synthesize, turn, answer, index, text)
            except Exception:  # 一段合成失敗只跳過這段
                logger.exception("答案語音合成失敗，跳過這一段：%s", text)
                continue
            if seconds <= 0:
                logger.warning("答案這一段驗收不過，跳過：%s", text)
                continue
            answer.segments.append(AnswerSegment(index, seconds))
            if index == 0:
                self._record_latency(answer, self._monotonic() - started)

    def _active(self, answer: Answer) -> bool:
        """答案還在進行、也還沒被淘汰：失敗或被淘汰的答案不再合成、不再寫檔。"""
        return answer.status == "answering" and self._answers.get(answer.id) is answer

    def _synthesize(self, turn: AnswerTurnLike, answer: Answer, index: int, text: str) -> float:
        if not self._active(answer):
            return 0.0
        result = turn.run(text)
        if result.audio_seconds <= 0 or not self._active(answer):
            return 0.0
        path = self._segment_path(answer.id, index)
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
        except Exception:  # 記錄只是附帶的，不能讓答案因此卡住
            logger.exception("問答延遲記錄寫入失敗")

    async def _context(
        self, question: str, fix: TourFix, more: bool, photo: PhotoInput | None
    ) -> AskContext:
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
            photo=photo,
        )

    @staticmethod
    def _fail(answer: Answer, reason: str) -> None:
        answer.status = "failed"
        answer.reason = reason
