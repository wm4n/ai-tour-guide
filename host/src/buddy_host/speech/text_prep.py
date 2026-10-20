"""寫稿後、合成前的文字處理（KittenTTS 2 必須 normalize=False，所以全部自己來）。

spike 的發現：阿拉伯數字要先轉中文、日文假名要拿掉、中文句子要自己依「。！？」切。
"""

import re

_DIGITS = "零一二三四五六七八九"
_PLACES = ("千", "百", "十", "")
_CLOSERS = '」』）)”"'
_TERMINALS = "。！？"
_COMMA_ENDINGS = "，、；：,;:"

_KANA = "぀-ゟ゠-ヿㇰ-ㇿｦ-ﾟ"
_KANA_RE = re.compile(f"[{_KANA}]")
_QUOTED_KANA_RE = re.compile(f"[「『][^」』]*[{_KANA}][^」』]*[」』]")
_ASCII_PAREN_RE = re.compile(r"[（(]\s*([A-Za-z0-9][A-Za-z0-9 .,'\-]*?)\s*[）)]")
_CJK_LATIN_RE = re.compile(r"(?<=[一-鿿])(?=[A-Za-z])|(?<=[A-Za-z])(?=[一-鿿])")


def _group(n: int, *, liang: bool, omit_ten_one: bool) -> str:
    """1..9999 的讀法。"""
    digits = [n // 1000 % 10, n // 100 % 10, n // 10 % 10, n % 10]
    out: list[str] = []
    pending_zero = False
    for digit, place in zip(digits, _PLACES, strict=True):
        if digit == 0:
            pending_zero = pending_zero or bool(out)
            continue
        if pending_zero:
            out.append("零")
            pending_zero = False
        if place == "十" and digit == 1 and omit_ten_one and not out:
            out.append("十")
        elif digit == 2 and liang and place in ("千", "百"):
            out.append("兩" + place)
        else:
            out.append(_DIGITS[digit] + place)
    return "".join(out)


def _cardinal(n: int, *, liang: bool = True) -> str:
    if n == 0:
        return "零"
    if n == 2 and liang:
        return "兩"
    top, low = divmod(n, 10000)
    out = ""
    if top:
        out = "兩萬" if top == 2 and liang else _group(top, liang=liang, omit_ten_one=True) + "萬"
    if low:
        if top and low < 1000:
            out += "零"
        out += _group(low, liang=liang, omit_ten_one=not top)
    return out


def _by_digit(digits: str) -> str:
    return "".join(_DIGITS[int(d)] for d in digits)


def _number(raw: str, *, liang: bool = True) -> str:
    """純數字字串的讀法：前導零或過長用逐位唸，否則用基數。"""
    if len(raw) > 8 or (len(raw) > 1 and raw.startswith("0")):
        return _by_digit(raw)
    return _cardinal(int(raw), liang=liang)


def _decimal(whole: str, frac: str) -> str:
    return _number(whole) + "點" + _by_digit(frac)


def _clock(match: re.Match[str]) -> str:
    hour, minute = int(match[1]), int(match[2])
    out = _cardinal(hour) + "點"
    if minute:
        out += ("零" if minute < 10 else "") + _cardinal(minute, liang=False) + "分"
    return out


_NUM = r"\d+(?:\.\d+)?"
# 「1000年歷史」是長度不是年份
_DURATION_AFTER = "(?:歷史|的歷史|以上|多|之久)"


def _slash_date(match: re.Match[str]) -> str:
    month, day = int(match[1]), int(match[2])
    if 1 <= month <= 12 and 1 <= day <= 31:
        return f"{_cardinal(month, liang=False)}月{_cardinal(day, liang=False)}日"
    return match[0]


def _any_number(raw: str) -> str:
    whole, _, frac = raw.partition(".")
    return _decimal(whole, frac) if frac else _number(whole)


def numbers_to_chinese(text: str) -> str:
    text = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", text)
    text = re.sub(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)", _clock, text)
    text = re.sub(rf"({_NUM})\s*%", lambda m: "百分之" + _any_number(m[1]), text)
    text = re.sub(
        r"(?<!\d)(\d{4})\s*[～~〜–]\s*(\d{4})(?=年)",
        lambda m: _by_digit(m[1]) + "到" + _by_digit(m[2]),
        text,
    )
    text = re.sub(rf"(?<!\d)(\d{{4}})(?=年(?!{_DURATION_AFTER}))", lambda m: _by_digit(m[1]), text)
    text = re.sub(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])", _slash_date, text)
    text = re.sub(
        r"(?<!\d)(\d{1,2})(?=[月日號])", lambda m: _cardinal(int(m[1]), liang=False), text
    )
    text = re.sub(r"(?<=第)(\d+)", lambda m: _number(m[1], liang=False), text)
    text = re.sub(
        rf"({_NUM})\s*[～~〜–]\s*({_NUM})",
        lambda m: _any_number(m[1]) + "到" + _any_number(m[2]),
        text,
    )
    return re.sub(_NUM, lambda m: _any_number(m[0]), text)


def remove_kana(text: str) -> str:
    text = _QUOTED_KANA_RE.sub("", text)
    text = _KANA_RE.sub("", text)
    text = _ASCII_PAREN_RE.sub(r" \1 ", text)
    text = _CJK_LATIN_RE.sub(" ", text)
    text = re.sub(r"[ \t]+(?=[。！？，、；：])", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return "\n".join(line.strip() for line in text.split("\n"))


_SENTENCE_RE = re.compile(rf"[^{_TERMINALS}]*[{_TERMINALS}]+[{re.escape(_CLOSERS)}]*")


def split_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[-1] in _COMMA_ENDINGS:
            line = line[:-1] + "。"
        elif not re.search(rf"[{_TERMINALS}…][{re.escape(_CLOSERS)}]*$", line):
            line += "。"
        sentences.extend(s.strip() for s in _SENTENCE_RE.findall(line) if s.strip())
    return sentences


def prepare_sentences(text: str) -> list[str]:
    return split_sentences(numbers_to_chinese(remove_kana(text)))


def prepare_paragraphs(text: str) -> list[list[str]]:
    """空行分段；每段各自整理成句子。段落是講故事時「換一口氣」的地方，朗讀時停得比句間久。"""
    paragraphs = (prepare_sentences(block) for block in re.split(r"\n\s*\n", text))
    return [sentences for sentences in paragraphs if sentences]


def chunk_sentences(sentences: list[str], limit: int = 90) -> list[str]:
    """把相鄰句子併成每段約 limit 字：太短的句子（例如「哇！」）單獨合成很容易失敗。"""
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if current and len(current) + len(sentence) > limit:
            chunks.append(current)
            current = ""
        current += sentence
    if current:
        chunks.append(current)
    return chunks
