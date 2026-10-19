"""合成後以 Whisper 轉寫比對原稿的字元錯誤率（CER）。

Whisper 愛輸出阿拉伯數字（2027），原稿已轉成中文數字（二零二七），不統一會讓 CER 被誤判偏高。
"""

import re

from opencc import OpenCC

from buddy_host.speech.text_prep import numbers_to_chinese

_T2S = OpenCC("t2s")
_KEEP_RE = re.compile(r"[一-鿿a-z0-9]")
# 同音、聽不出差別的寫法：Whisper 會挑常用字（城隍→城黃、它→他），不能算唸錯
_HOMOPHONES = str.maketrans({"隍": "黄", "它": "他", "她": "他", "牠": "他", "祂": "他"})


def normalize(text: str) -> str:
    text = numbers_to_chinese(text)
    text = text.replace("兩", "二").replace("两", "二").replace("〇", "零")
    text = _T2S.convert(text).lower().translate(_HOMOPHONES)
    return "".join(_KEEP_RE.findall(text))


def _edit_distance(a: str, b: str) -> int:
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        previous, row[0] = row[0], i
        for j, cb in enumerate(b, start=1):
            current = row[j]
            row[j] = min(row[j] + 1, row[j - 1] + 1, previous + (ca != cb))
            previous = current
    return row[len(b)]


def cer(reference: str, hypothesis: str) -> float:
    ref, hyp = normalize(reference), normalize(hypothesis)
    if not ref:
        return 0.0
    return _edit_distance(ref, hyp) / len(ref)
