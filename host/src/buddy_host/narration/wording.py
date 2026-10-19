"""兩岸用語檢查：Claude 寫的稿要用台灣用語與繁體字（個性檔有寫規則，這裡再用程式把關一次）。

這份對照表只收「幾乎不會誤判」的詞，抓得到的是字詞，抓不到語氣或腔調。
"""

import json
from dataclasses import dataclass
from pathlib import Path

from opencc import OpenCC

DEFAULT_TERMS_FILE = Path(__file__).resolve().parents[3] / "config" / "taiwan_terms.json"
SIMPLIFIED_LABEL = "簡體字"
# 「里」「后」這類字繁簡共用，單獨出現不代表是簡體；要有好幾個才算
_SIMPLIFIED_MIN_CHANGES = 3
_S2T = OpenCC("s2t")


@dataclass(frozen=True)
class Finding:
    term: str
    suggestion: str


def load_terms(path: Path = DEFAULT_TERMS_FILE) -> list[tuple[str, str]]:
    entries = json.loads(path.read_text(encoding="utf-8"))
    return [(e["mainland"], e["taiwan"]) for e in entries]


def _looks_simplified(text: str) -> bool:
    converted = _S2T.convert(text)
    changed = sum(1 for a, b in zip(text, converted, strict=False) if a != b)
    return changed >= _SIMPLIFIED_MIN_CHANGES


def find_issues(text: str, terms: list[tuple[str, str]]) -> list[Finding]:
    issues: list[Finding] = []
    remaining = text
    # 長詞先比對並遮掉，避免「公交車」同時報「公交」
    for mainland, taiwan in sorted(terms, key=lambda t: -len(t[0])):
        if mainland in remaining:
            issues.append(Finding(mainland, taiwan))
            remaining = remaining.replace(mainland, "　")
    if _looks_simplified(text):
        issues.append(Finding(SIMPLIFIED_LABEL, "改用繁體中文"))
    return issues
