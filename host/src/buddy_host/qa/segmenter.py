"""把串流中的答案文字切成要合成的段落（設計文件第 8 節：第一句要短，合成並驗收好就先播）。

- 只在句子寫完（。！？或換行）之後才吐出，所以不會把半句話拿去合成。
- 第一段盡量短：寫完第一句就吐出（太短的句子單獨合成容易驗收失敗，會先併入下一句）。
- 之後的段落併到約 `later_max_chars` 字：合成比播放慢，段落不宜太長，否則兩段之間會等很久。
"""

import re

_SENTENCE_RE = re.compile(r"[^。！？\n]*(?:[。！？]+[」』）)”\"]*|\n)")

MIN_FIRST_CHARS = 10
LATER_MAX_CHARS = 60


class AnswerSegmenter:
    def __init__(
        self, *, min_first_chars: int = MIN_FIRST_CHARS, later_max_chars: int = LATER_MAX_CHARS
    ):
        self._min_first = min_first_chars
        self._later_max = later_max_chars
        self._buffer = ""  # 還沒寫完的句子
        self._open = ""  # 寫完了、但還沒吐出的句子
        self._emitted = 0

    def feed(self, text: str) -> list[str]:
        self._buffer += text
        ready: list[str] = []
        consumed = 0
        for match in _SENTENCE_RE.finditer(self._buffer):
            consumed = match.end()
            sentence = match.group().strip()
            if sentence:
                ready += self._add(sentence)
        self._buffer = self._buffer[consumed:]
        return ready

    def finish(self) -> list[str]:
        """答案寫完了：連沒有句尾標點的最後一段也吐出來。"""
        ready: list[str] = []
        tail = self._buffer.strip()
        self._buffer = ""
        if tail:
            ready += self._add(tail)
        ready += self._emit()
        return ready

    def discard(self) -> None:
        """丟掉還沒吐出的文字（例如 Claude 上網查之前先說的開場白）；已吐出的收不回來。"""
        self._buffer = ""
        self._open = ""

    def _add(self, sentence: str) -> list[str]:
        ready: list[str] = []
        if self._emitted and self._open and len(self._open) + len(sentence) > self._later_max:
            ready += self._emit()
        self._open += sentence
        if self._emitted == 0 and len(self._open) >= self._min_first:
            ready += self._emit()
        elif self._emitted and len(self._open) >= self._later_max:
            ready += self._emit()
        return ready

    def _emit(self) -> list[str]:
        if not self._open:
            return []
        segment, self._open = self._open, ""
        self._emitted += 1
        return [segment]
