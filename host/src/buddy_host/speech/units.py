"""從合成好的 wav 找出各個「合成單位」的起點（設計文件第 8 節：被打斷的介紹從那一句開頭接著講）。

語音管線在單位之間插入的是精確的靜音（全 0 樣本，`SpeechPipeline._silence`），模型自己產生的聲音
即使很安靜也不會連續幾百毫秒都剛好是 0，所以直接從 wav 偵測就行；快取裡舊的介紹也一樣能用，
不必改快取格式。單位內部真的出現的短暫靜音（小於 `min_gap_seconds`）不算邊界。
"""

import logging
import wave
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

MIN_GAP_SECONDS = 0.3  # 管線的單位間隔是 0.45 秒起（`PipelineConfig.gap_seconds`）


def unit_starts(path: Path, *, min_gap_seconds: float = MIN_GAP_SECONDS) -> tuple[float, ...]:
    """每個單位開始播放的秒數，依序；讀不到或整段都是靜音時回傳空的。"""
    try:
        with wave.open(str(path), "rb") as wav:
            rate = wav.getframerate()
            width = wav.getsampwidth()
            raw = wav.readframes(wav.getnframes())
        if width != 2:
            return ()
        samples = np.frombuffer(raw, dtype="<i2")
    except (OSError, EOFError, wave.Error):
        logger.warning("讀不到 %s，沒有各句的起點時間", path)
        return ()

    voiced = np.flatnonzero(samples != 0)
    if voiced.size == 0:
        return ()
    min_gap = max(1, int(min_gap_seconds * rate))
    # 有聲樣本之間的空隙（＝連續的 0）夠長，空隙之後的第一個有聲樣本就是新單位的起點
    gaps = np.diff(voiced)
    starts = [voiced[0], *voiced[1:][gaps > min_gap]]
    return tuple(round(float(start) / rate, 2) for start in starts)
