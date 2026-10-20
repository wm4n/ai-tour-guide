import numpy as np

from buddy_host.speech.pipeline import SpeechResult


class FakeSpeech:
    """假的語音管線：記下每次要合成的文字；`skip` 裡的文字當作驗收不過（沒有音訊）。"""

    def __init__(self, seconds: float = 2.0, skip=(), explode=()):
        self.seconds = seconds
        self.skip = set(skip)
        self.explode = set(explode)
        self.texts: list[str] = []

    def run(self, text: str) -> SpeechResult:
        self.texts.append(text)
        if text in self.explode:
            raise RuntimeError("引擎壞了")
        seconds = 0 if text in self.skip else self.seconds
        return SpeechResult(np.full(int(seconds * 1000), 0.1, dtype=np.float32), 1000, [], 0.5)
