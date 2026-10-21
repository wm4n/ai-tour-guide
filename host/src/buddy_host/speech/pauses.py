"""壓縮過長的停頓：讓回答聽起來像聊天，而不是一句一句慢慢唸。

模型自己會在句間、句中停很久（同一份稿子靜音可達三成以上）。這裡只縮短靜音，
說話的部分一個取樣都不動。靜音的判斷與 librosa.effects.split 相同（以整段最大音量為基準，
低於 top_db 算靜音），只是不依賴 librosa，主機的一般安裝也能用。
"""

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

# librosa 在 24 kHz 的預設（1024／256 個取樣），換成秒，其他取樣率也是同樣的時間解析度
FRAME_SECONDS = 1024 / 24_000
HOP_SECONDS = 256 / 24_000
TOP_DB = 35.0


def cap_pauses(audio: np.ndarray, sample_rate: int, max_pause_seconds: float) -> np.ndarray:
    """說話之間超過 `max_pause_seconds` 的靜音縮到這個長度；開頭與結尾各留一半。"""
    spans = _speech_spans(audio, sample_rate)
    if not spans:
        return audio
    cap = int(max_pause_seconds * sample_rate)
    edge = cap // 2
    parts = [audio[max(0, spans[0][0] - edge) : spans[0][0]]]
    for (start, end), (next_start, _) in zip(spans, spans[1:], strict=False):
        parts.append(audio[start:end])
        gap = audio[end:next_start]
        if len(gap) > cap:
            gap = np.concatenate([gap[: cap // 2], gap[len(gap) - (cap - cap // 2) :]])
        parts.append(gap)
    last_end = spans[-1][1]
    parts += [audio[spans[-1][0] : last_end], audio[last_end : last_end + edge]]
    out = np.concatenate(parts)
    return audio if len(out) == len(audio) else out


def _speech_spans(audio: np.ndarray, sample_rate: int) -> list[tuple[int, int]]:
    if len(audio) == 0:
        return []
    frame = max(2, round(FRAME_SECONDS * sample_rate))
    hop = max(1, round(HOP_SECONDS * sample_rate))
    padded = np.pad(audio.astype(np.float64), frame // 2)
    if len(padded) < frame:
        padded = np.pad(padded, (0, frame - len(padded)))
    frames = sliding_window_view(padded, frame)[::hop]
    power = np.mean(frames**2, axis=1)
    peak = power.max()
    if peak <= 0:
        return []
    loud = 10 * np.log10(np.maximum(power, 1e-10) / peak) > -TOP_DB
    edges = np.flatnonzero(np.diff(loud.astype(np.int8))) + 1
    if loud[0]:
        edges = np.r_[0, edges]
    if loud[-1]:
        edges = np.r_[edges, len(loud)]
    samples = np.minimum(edges * hop, len(audio))
    return [(int(s), int(e)) for s, e in samples.reshape(-1, 2) if e > s]
