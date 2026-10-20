"""重播模式的假問答：固定的答案文字、一段一段的提示音，不呼叫 Claude、不載入語音模型。

和 `tour.replay` 一樣，只用來在桌上（例如 iOS 模擬器）把 App 的問答流程跑通，不消耗額度。
"""

import numpy as np

from buddy_host.llm.models import LlmRequest, LlmResult
from buddy_host.places.models import Location
from buddy_host.speech.pipeline import SpeechResult

ANSWER_PIECES = (
    "這是重播模式的固定答案，",
    "不管你問什麼都是這一句。",
    "第二句也是固定的，只是用來測試。",
)
SAMPLE_RATE = 24000


class CannedLlm:
    """依序串流固定的答案；問題裡提到「上網」時，假裝 Claude 動用了上網工具。"""

    async def run(self, request: LlmRequest, on_text=None, on_tool=None) -> LlmResult:
        if on_tool and "上網" in request.prompt:
            on_tool("WebSearch")
        for piece in ANSWER_PIECES:
            if on_text:
                on_text(piece)
        return LlmResult("".join(ANSWER_PIECES), "replay", {}, {}, {}, 0)


class NoNearby:
    async def nearby(self, location: Location, *, limit: int = 5) -> list:
        return []


class _Turn:
    def __init__(self, speech: "ToneSpeech"):
        self._speech = speech

    def run(self, text: str) -> SpeechResult:
        return self._speech.run(text)

    def end(self) -> None:
        pass


class ToneSpeech:
    """每一段都回一小段提示音（聽得到、分得出有幾段），不管文字是什麼。"""

    def __init__(self, seconds: float = 1.5, frequency: float = 440.0):
        self._seconds = seconds
        self._frequency = frequency

    def begin(self) -> _Turn:
        return _Turn(self)

    def run(self, text: str) -> SpeechResult:
        t = np.arange(int(SAMPLE_RATE * self._seconds)) / SAMPLE_RATE
        fade = np.minimum(1.0, np.minimum(t, self._seconds - t) / 0.05)  # 頭尾淡入淡出，不爆音
        audio = (0.2 * np.sin(2 * np.pi * self._frequency * t) * fade).astype(np.float32)
        return SpeechResult(audio, SAMPLE_RATE, [], 0.0)
