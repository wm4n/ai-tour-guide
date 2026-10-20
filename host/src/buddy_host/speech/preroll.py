"""句首檢查：Whisper 常把句首的語助詞（呃、啊、阿）當雜音省略，CER 看不到，但耳朵聽得到。

用逐字時間戳記找出：第一個詞是不是原稿的開頭、開口前有沒有一段多餘的聲音，必要時裁掉。
"""

from dataclasses import dataclass

from buddy_host.speech.cer import normalize

FILLERS = frozenset("啊阿呃嗯欸喔哦哇")
MAX_LEAD_SECONDS = 0.3  # 開口前允許的空白（一句話開頭本來就會有一點呼吸）
TRIM_MARGIN_SECONDS = 0.15  # 逐字時間戳記不精準，裁的時候往前多留一點，免得切掉第一個音


@dataclass(frozen=True)
class WordTiming:
    word: str
    start: float
    end: float


@dataclass(frozen=True)
class PrerollVerdict:
    ok: bool
    reason: str | None = None
    trim_to: float | None = None  # 從這個秒數開始留下；None 表示不用裁


def _first_char(text: str) -> str:
    return normalize(text)[:1]


def analyze_preroll(expected: str, words: list[WordTiming]) -> PrerollVerdict:
    spoken = [(normalize(w.word), w) for w in words if normalize(w.word)]
    if not spoken:
        return PrerollVerdict(False, "no words recognised")

    head = _first_char(expected)
    first_text, first = spoken[0]

    if first_text[0] in FILLERS and head != first_text[0]:
        for text, word in spoken[1:]:
            if text.startswith(head):
                trim_to = max(0.0, word.start - TRIM_MARGIN_SECONDS)
                return PrerollVerdict(True, f"leading filler {first_text!r} cut", trim_to)
        return PrerollVerdict(False, f"leading filler {first_text!r}, expected start not found")

    if not first_text.startswith(head):
        return PrerollVerdict(False, f"first word {first_text!r} does not match expected {head!r}")

    if first.start > MAX_LEAD_SECONDS:
        trim_to = max(0.0, first.start - TRIM_MARGIN_SECONDS)
        return PrerollVerdict(True, f"lead-in {first.start:.2f}s cut", trim_to)
    return PrerollVerdict(True)
