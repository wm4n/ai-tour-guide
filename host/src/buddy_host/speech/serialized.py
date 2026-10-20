"""讓同一個語音管線一次只被一個執行緒使用（只有一顆 GPU、模型只載入一份）。"""

import threading

from buddy_host.speech.pipeline import SpeechResult


class SerializedSpeech:
    def __init__(self, inner):
        self._inner = inner
        self._lock = threading.Lock()

    def run(self, text: str) -> SpeechResult:
        with self._lock:
            return self._inner.run(text)
