"""用能量找出「真正開口」的位置。

合成單位的開頭常有一小段低音量的聲音（約 -25～-33 dB），接著近乎靜音，約 0.45 秒後才開口。
Whisper 的逐字時間戳記對這段不準（會把第一個字標在前導裡），所以改看音量：
開口 = 音量連續夠大的第一個位置，門檻是這段音訊本身說話音量（第 90 百分位）往下 15 dB。
"""

import math

import numpy as np

FRAME_SECONDS = 0.02
DROP_DB = 15.0
MIN_SUSTAIN_SECONDS = 0.08  # 一聲短促的喀聲不算開口
DEFAULT_MARGIN_SECONDS = 0.08  # 開口點往前多留一點，免得切掉第一個音
_SILENT_RMS = 1e-6


def speech_onset(audio: np.ndarray, sample_rate: int) -> float:
    frame = max(1, int(sample_rate * FRAME_SECONDS))
    count = len(audio) // frame
    if count == 0:
        return 0.0
    chunks = audio[: count * frame].reshape(count, frame).astype(np.float64)
    rms = np.sqrt(np.mean(chunks**2, axis=1))
    voiced = rms > _SILENT_RMS
    if not voiced.any():
        return 0.0
    db = 20 * np.log10(rms + 1e-9)
    threshold = np.percentile(db[voiced], 90) - DROP_DB
    needed = math.ceil(MIN_SUSTAIN_SECONDS / FRAME_SECONDS)
    loud = db >= threshold
    for i in range(count - needed + 1):
        if loud[i : i + needed].all():
            return i * FRAME_SECONDS
    return 0.0


def trim_lead(
    audio: np.ndarray, sample_rate: int, margin: float = DEFAULT_MARGIN_SECONDS
) -> tuple[np.ndarray, float]:
    cut = speech_onset(audio, sample_rate) - margin
    if cut <= 0:
        return audio, 0.0
    return audio[int(round(cut * sample_rate)) :], cut
