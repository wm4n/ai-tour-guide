"""語音合成的排程（設計文件第 9.1 節）：家中 Mac 只有一顆 GPU，問答優先，主動介紹在單位之間讓路。

- 「合成單位」是語音管線裡的一個 chunk（含它的換 seed 重試）；正在合成的單位不會被打斷。
- 介紹每個單位開始前先看有沒有問答在排隊，有就等；問答全部做完才繼續，所以介紹最終一定會完成。
- 問答依先後順序一個一個來（一次 `answers.run` 從頭做到尾，中間不讓介紹插進來），不會同時合成。
- 兩邊都在各自的執行緒裡呼叫（`asyncio.to_thread`），排程用 Condition 協調。
"""

import threading
from contextlib import contextmanager

from buddy_host.speech.pipeline import SpeechPipeline, SpeechResult


class _Narration:
    def __init__(self, scheduler: "SpeechScheduler"):
        self._scheduler = scheduler

    def run(self, text: str) -> SpeechResult:
        return self._scheduler._pipeline.run(text, unit_guard=self._scheduler._narration_unit)


class _Answers:
    def __init__(self, scheduler: "SpeechScheduler"):
        self._scheduler = scheduler

    def run(self, text: str) -> SpeechResult:
        with self._scheduler._answer_turn():
            return self._scheduler._pipeline.run(text)


class SpeechScheduler:
    def __init__(self, pipeline: SpeechPipeline):
        self._pipeline = pipeline
        self._cond = threading.Condition()
        self._tickets = 0  # 已經發出去的問答號碼牌
        self._served = 0  # 已經做完（或放棄）的問答數
        self._narration_busy = False  # 有一個介紹單位正在合成
        self.narration = _Narration(self)  # `run(text)`：主動介紹用，單位之間讓路
        self.answers = _Answers(self)  # `run(text)`：問答用，優先

    @property
    def pending_answers(self) -> int:
        """正在合成或排隊中的問答數。"""
        with self._cond:
            return self._tickets - self._served

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

    @contextmanager
    def _answer_turn(self):
        with self._cond:
            ticket = self._tickets
            self._tickets += 1  # 號碼牌一發出去，介紹就不會再開始新的單位
            # 輪到我、而且介紹正在合成的那個單位已經做完
            self._cond.wait_for(lambda: self._served == ticket and not self._narration_busy)
        try:
            yield
        finally:
            with self._cond:
                self._served += 1
                self._cond.notify_all()
