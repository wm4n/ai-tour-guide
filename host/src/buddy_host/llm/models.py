"""LLM 介接層的共用型別與模型政策（設計文件第 5 節：Sonnet 寫稿／問答、Haiku 判斷、禁用 Fable）。"""

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class Purpose(StrEnum):
    WRITE = "write"
    QA = "qa"
    JUDGE = "judge"
    PROBE = "probe"


DEFAULT_MODELS = {
    Purpose.WRITE: "sonnet",
    Purpose.QA: "sonnet",
    Purpose.JUDGE: "haiku",
    Purpose.PROBE: "haiku",
}

_ALIASES = {"sonnet", "haiku", "opus"}
_FULL_ID_RE = re.compile(r"^claude-(sonnet|haiku|opus)-[\w.\-]+(\[1m\])?$")


class ForbiddenModelError(ValueError):
    pass


def is_fable(name: str) -> bool:
    return "fable" in name.lower()


def resolve_model(purpose: Purpose, override: str | None) -> str:
    if override is None:
        return DEFAULT_MODELS[purpose]
    if is_fable(override):
        raise ForbiddenModelError(f"不可使用 Fable：{override}")
    if override in _ALIASES or _FULL_ID_RE.match(override):
        return override
    raise ForbiddenModelError(f"未允許的模型：{override!r}（只接受 sonnet／haiku／opus）")


@dataclass(frozen=True)
class LlmRequest:
    prompt: str
    purpose: Purpose
    model: str | None = None
    system_prompt: str | None = None
    mcp_config: Path | None = None
    allowed_tools: tuple[str, ...] = ()
    add_dirs: tuple[Path, ...] = ()
    timeout: float | None = None


@dataclass(frozen=True)
class LlmResult:
    text: str
    model: str
    usage: dict
    model_usage: dict
    rate_limit: dict
    duration_ms: int | None
