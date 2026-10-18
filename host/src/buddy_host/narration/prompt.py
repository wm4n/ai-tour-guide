"""替 Claude 組出「寫一段介紹稿」的請求。個性與寫作規則整份放在 config/buddy.md，每次都重讀。"""

from dataclasses import dataclass
from pathlib import Path

from buddy_host.llm.models import LlmRequest, Purpose
from buddy_host.places.models import Candidate

WEB_TOOLS = ("WebSearch", "WebFetch")
THIN_FACTS_CHARS = 80
_INTERESTING_TAGS = (
    "tourism", "historic", "amenity", "shop", "craft", "heritage", "start_date",
    "description", "operator", "cuisine",
)  # fmt: skip


@dataclass(frozen=True)
class ScriptContext:
    candidate: Candidate
    wiki_extract: str | None
    distance_m: float
    bearing_relative_deg: float | None  # 相對行進方向：0＝正前方，正值偏右
    told_before: tuple[str, ...] = ()  # 以前跟使用者講過這個地方的重點
    recent_topics: tuple[str, ...] = ()  # 這趟剛講過的主題，用來對比串連


def load_persona(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def describe_direction(relative_deg: float | None) -> str:
    if relative_deg is None:
        return "附近"
    d = (relative_deg + 180) % 360 - 180
    side = "右" if d > 0 else "左"
    magnitude = abs(d)
    if magnitude <= 22.5:
        return "正前方"
    if magnitude <= 67.5:
        return f"{side}前方"
    if magnitude <= 112.5:
        return f"{side}手邊"
    if magnitude <= 157.5:
        return f"{side}後方"
    return "後方"


def _facts(ctx: ScriptContext) -> str:
    tags = "；".join(
        f"{k}={ctx.candidate.tags[k]}" for k in _INTERESTING_TAGS if ctx.candidate.tags.get(k)
    )
    lines = [f"地點：{ctx.candidate.name}"]
    if tags:
        lines.append(f"OpenStreetMap 資訊：{tags}")
    lines.append(
        f"維基百科摘要：{ctx.wiki_extract}" if ctx.wiki_extract else "維基百科摘要：（沒有）"
    )
    return "\n".join(lines)


def build_script_request(
    persona: str,
    ctx: ScriptContext,
    *,
    seconds: tuple[int, int] = (30, 45),
    model: str | None = None,
) -> LlmRequest:
    thin = not ctx.wiki_extract or len(ctx.wiki_extract) < THIN_FACTS_CHARS
    parts = [
        f"我們正走到「{ctx.candidate.name}」，它在{describe_direction(ctx.bearing_relative_deg)}"
        f"約 {ctx.distance_m:.0f} 公尺。請為它寫一段 {seconds[0]} 到 {seconds[1]} 秒的口說介紹。",
        _facts(ctx),
    ]
    if ctx.told_before:
        parts.append(
            "這個地方我們以前講過了：\n"
            + "\n".join(f"- {t}" for t in ctx.told_before)
            + "\n今天請換個角度講，不要重複。"
        )
    if ctx.recent_topics:
        parts.append("這趟剛介紹過：" + "、".join(ctx.recent_topics) + "。可以拿來對比或串連。")
    if thin:
        parts.append("上面的資料不多，你可以上網查證補充，但查不到的事不要編。")
    parts.append("只輸出要唸出來的稿子，不要任何前言、標題或說明。")
    return LlmRequest(
        prompt="\n\n".join(parts),
        purpose=Purpose.WRITE,
        model=model,
        system_prompt=persona,
        allowed_tools=WEB_TOOLS if thin else (),
    )
