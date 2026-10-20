"""語音合成的排程（設計文件第 9.1 節）：家中 Mac 只有一顆 GPU，問答優先，主動介紹在單位之間讓路。

- 「合成單位」是語音管線裡的一個 chunk（含它的換 seed 重試）；正在合成的單位不會被打斷。
- 介紹每個單位開始前先看有沒有問答在排隊或進行，有就等；問答全部做完才繼續，所以介紹最終一定會完成。
- 一個問答從開始回答（`answers.begin()`）到結束（`turn.end()`）整段持有優先權，包含等 Claude
  寫下一段的空檔：介紹不會趁機開始新單位，否則下一段問答就得再等一個介紹單位。
- 問答依先後順序一個一個來，不會同時合成；介紹與問答、兩個介紹之間，也一次只合成一個單位。
- 兩邊都在各自的執行緒裡呼叫（`asyncio.to_thread`），排程用 Condition 協調。
"""

import threading
from contextlib import contextmanager

from buddy_host.speech.pipeline import SpeechPipeline, SpeechResult


class TurnEnded(RuntimeError):
    """這個問答已經結束（例如答案被放棄），不再合成。"""


class AnswerTurn:
    """一個問答在排程器裡的位置。用 `run(text)` 合成每一段答案，答案結束或放棄時呼叫 `end()`。"""

    def __init__(self, scheduler: "SpeechScheduler", ticket: int):
        self._scheduler = scheduler
        self._ticket = ticket
        self._ended = False
        self._running = False
        self._released = False

    def run(self, text: str) -> SpeechResult:
        """輪到這個問答、且介紹正在合成的單位做完之後才開始；等待中被 `end()` 就拋 TurnEnded。"""
        scheduler = self._scheduler
        with scheduler._cond:
            scheduler._cond.wait_for(
                lambda: (
                    self._ended
                    or (scheduler._served == self._ticket and not scheduler._narration_busy)
                )
            )
            if self._ended:
                raise TurnEnded("問答已結束")
            self._running = True
        try:
            return scheduler._pipeline.run(text)
        finally:
            with scheduler._cond:
                self._running = False
                scheduler._release_if_finished(self)

    def end(self) -> None:
        """答案做完、失敗或放棄。重複呼叫沒有影響；還有一段在合成時，等它做完才真的讓出 GPU。"""
        scheduler = self._scheduler
        with scheduler._cond:
            self._ended = True
            scheduler._release_if_finished(self)
            scheduler._cond.notify_all()


class _Answers:
    def __init__(self, scheduler: "SpeechScheduler"):
        self._scheduler = scheduler

    def begin(self) -> AnswerTurn:
        """開始一個問答，立刻取得優先順位（不阻塞）；介紹從現在起不會開始新的單位。"""
        return self._scheduler.begin_answer()

    def run(self, text: str) -> SpeechResult:
        """單一段文字的問答：取號、合成、結束。"""
        turn = self.begin()
        try:
            return turn.run(text)
        finally:
            turn.end()


class _Narration:
    def __init__(self, scheduler: "SpeechScheduler"):
        self._scheduler = scheduler

    def run(self, text: str) -> SpeechResult:
        return self._scheduler.run_narration(text)


class SpeechScheduler:
    def __init__(self, pipeline: SpeechPipeline):
        self._pipeline = pipeline
        self._cond = threading.Condition()
        self._tickets = 0  # 已經發出去的問答號碼牌
        self._served = 0  # 已經輪完的問答數（號碼牌依序輪）
        self._finished: set[int] = set()  # 已經做完、但前面還有人沒輪完的號碼牌
        self._narration_busy = False  # 有一個介紹單位正在合成
        self.narration = _Narration(self)  # `run(text)`：主動介紹用，單位之間讓路
        self.answers = _Answers(self)  # `begin()`／`run(text)`：問答用，優先

    @property
    def pending_answers(self) -> int:
        """進行中或排隊中的問答數。"""
        with self._cond:
            return self._tickets - self._served

    def run_narration(self, text: str) -> SpeechResult:
        return self._pipeline.run(text, unit_guard=self._narration_unit)

    def begin_answer(self) -> AnswerTurn:
        with self._cond:
            ticket = self._tickets
            self._tickets += 1  # 號碼牌一發出去，介紹就不會再開始新的單位
            return AnswerTurn(self, ticket)

    @contextmanager
    def _narration_unit(self):
        with self._cond:
            self._cond.wait_for(lambda: self._tickets == self._served and not self._narration_busy)
            self._narration_busy = True
        try:
            yield
        finally:
            with self._cond:
                self._narration_busy = False
                self._cond.notify_all()

    def _release_if_finished(self, turn: AnswerTurn) -> None:
        """（持有 `_cond`）問答結束、而且沒有一段還在合成時，才把它的位置讓出去。"""
        if turn._ended and not turn._running and not turn._released:
            turn._released = True
            self._finished.add(turn._ticket)
            while self._served in self._finished:
                self._finished.discard(self._served)
                self._served += 1
            self._cond.notify_all()
