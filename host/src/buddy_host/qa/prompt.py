"""替 Claude 組出「回答使用者問題」的請求（設計文件第 8 節）。

個性與寫作規則沿用 config/buddy.md（寫稿用的整份系統提示），後面接問答專用的指示；
每次都是新的一段對話，旅程上下文（位置、附近景點、講過什麼）全部寫在這一份 prompt 裡。
"""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

from buddy_host.llm.models import LlmRequest, Purpose
from buddy_host.narration.prompt import WEB_TOOLS, ScriptContext, describe_direction, facts_text
from buddy_host.narration.traveler import TravelerContext
from buddy_host.places.models import Location

EXTRACT_CHARS = 200  # 每個附近景點的維基摘要上限；問答要快，不必把整篇條目塞進去
_COMPASS = ("北", "東北", "東", "東南", "南", "西南", "西", "西北")

QA_INSTRUCTIONS = """\
## 現在是問答，不是主動介紹

他剛剛用語音問了你一個問題。上面的個性與寫作規則照舊，但這一次：

- 直接回答他問的事，先講結論；不要重述他的問題，也不要先稱讚問題。
- 第一句要短（二十字以內），讓人可以馬上開始聽；整個回答以 80 到 150 字為準。
  他要求再多說一點時才可以長一些，最多 250 字。
- 提示裡的資料夠回答就直接答。問到最新的事（營業時間、活動、價格），或資料裡沒有的，才上網查。
- 要上網查時，查之前不要先說任何話，查完再直接回答。
- 查不到或沒把握，就老實說不太確定；不確定的事不要編。
- 「左邊」「右邊」「前面」以他的行進方向為準；提示說行進方向未知時，就不要講左右。
- 有附照片時，照片是他用手機對著眼前的東西拍的：先用 Read 工具看照片，再回答他問的事
  （例如「這是什麼」就直接說這是什麼、有什麼來歷）；不要把照片逐項描述一遍，也不要提到檔案或路徑。
- 只輸出要唸出來的回答，不要任何前言、標題或說明。"""


@dataclass(frozen=True)
class PhotoInput:
    """拍照提問的照片：主機上的檔案，加上拍照時的指南針方向（度，0＝北；讀不到時是 None）。"""

    path: Path
    compass_deg: float | None


@dataclass(frozen=True)
class AskContext:
    question: str
    location: Location
    traveler: TravelerContext | None
    nearby: tuple[ScriptContext, ...] = ()  # 附近值得一提的地方（含維基摘要）
    recent_topics: tuple[str, ...] = ()  # 這趟剛介紹過的地方
    told_before: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # 景點 id → 以前講過
    last_told: tuple[str, str] | None = None  # 剛剛播完的那段（地方名、稿子）
    more: bool = False  # 「再多說一點」
    photo: PhotoInput | None = None  # 拍照提問


def describe_compass(degrees: float) -> str:
    return _COMPASS[round((degrees % 360) / 45) % 8]


def _clip(text: str | None, limit: int) -> str | None:
    if text is None or len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _position(location: Location, photo: PhotoInput | None = None) -> str:
    where = f"他現在的位置：緯度 {location.lat:.4f}、經度 {location.lon:.4f}"
    if photo is not None:
        # 拿著手機拍照時，「前方、左右」以手機對著的方向為準（指南針），不是走路的方向
        if photo.compass_deg is None:
            return where + "，拍照的方向不明。"
        direction = describe_compass(photo.compass_deg)
        return where + f"，他拿著手機對著{direction}方向拍照（指南針），前後左右以那個方向為準。"
    if location.heading_deg is None:
        return where + "，行進方向未知。"
    return where + f"，正朝{describe_compass(location.heading_deg)}走。"


def _photo_section(photo: PhotoInput | None) -> list[str]:
    if photo is None:
        return []
    return [f"他附了一張剛拍的照片，檔案在 {photo.path}。請先用 Read 工具看這張照片，再回答。"]


def _nearby_section(ctx: AskContext) -> list[str]:
    if not ctx.nearby:
        return ["附近沒有查到值得一提的地方；就依你知道的、或上網查到的回答。"]
    blocks = []
    for index, place in enumerate(ctx.nearby, start=1):
        clipped = replace(place, wiki_extract=_clip(place.wiki_extract, EXTRACT_CHARS))
        direction = describe_direction(place.bearing_relative_deg)
        blocks.append(
            f"{index}. 在{direction}約 {place.distance_m:.0f} 公尺\n{facts_text(clipped)}"
        )
    return ["他附近的地方（方位以他的行進方向為準）：\n\n" + "\n\n".join(blocks)]


def _journey_section(ctx: AskContext) -> list[str]:
    parts = []
    if ctx.recent_topics:
        parts.append("這趟剛介紹過：" + "、".join(ctx.recent_topics) + "。可以拿來對比或串連。")
    for place in ctx.nearby:
        told = ctx.told_before.get(place.candidate.id)
        if told:
            parts.append(
                f"「{place.candidate.name}」我們以前講過：\n" + "\n".join(f"- {t}" for t in told)
            )
    return parts


def _more_section(ctx: AskContext) -> list[str]:
    if not ctx.more:
        return []
    if ctx.last_told is None:
        return ["他想再多聽一點，不過這趟還沒有播過任何介紹：請就他附近的地方自然地聊。"]
    name, script = ctx.last_told
    return [
        f"他剛聽完你講的「{name}」：\n{script}\n"
        "他想再多聽一點：請接著講還沒講過的部分，不要重複上面已經講過的。"
    ]


def build_answer_request(persona: str, ctx: AskContext) -> LlmRequest:
    parts = [f"他剛剛問你：「{ctx.question}」", _position(ctx.location, ctx.photo)]
    parts += _photo_section(ctx.photo)
    state = ctx.traveler.describe() if ctx.traveler else []
    if state:
        parts.append(
            "他現在的狀態：\n"
            + "\n".join(f"- {line}" for line in state)
            + "\n請依這個狀態調整說法與內容。"
        )
    parts += _nearby_section(ctx) + _journey_section(ctx) + _more_section(ctx)
    return LlmRequest(
        prompt="\n\n".join(parts),
        purpose=Purpose.QA,
        model="sonnet",  # 問答只用 Sonnet（設計文件第 5.2 節）；不接受外部覆寫
        system_prompt=f"{persona}\n\n{QA_INSTRUCTIONS}",
        # 讀照片要 Read 工具並開放照片所在的資料夾（做法見 docs/spikes/2026-10-19-claude-headless）
        allowed_tools=(WEB_TOOLS + ("Read",)) if ctx.photo else WEB_TOOLS,
        add_dirs=(ctx.photo.path.parent,) if ctx.photo else (),
    )
