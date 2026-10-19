import numpy as np
import pytest

from buddy_host.speech.onset import speech_onset, trim_lead

SR = 1000


def tone(seconds: float, amplitude: float) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (amplitude * np.sin(2 * np.pi * 50 * t)).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype=np.float32)


def test_onset_skips_a_faint_blip_and_the_quiet_gap_after_it():
    # 真實案例：合成單位開頭有一小段 -25 dB 左右的聲音，之後近乎靜音，約 0.45 秒才開口
    audio = np.concatenate([tone(0.1, 0.03), tone(0.3, 0.002), tone(1.0, 0.5)])

    assert speech_onset(audio, SR) == pytest.approx(0.4, abs=0.04)


def test_speech_that_starts_immediately_has_onset_zero():
    assert speech_onset(tone(1.0, 0.5), SR) == 0.0


def test_a_short_loud_click_is_not_mistaken_for_speech():
    audio = np.concatenate([tone(0.02, 0.5), silence(0.3), tone(1.0, 0.5)])

    assert speech_onset(audio, SR) == pytest.approx(0.32, abs=0.04)


def test_trim_lead_keeps_a_margin_before_the_first_phoneme():
    audio = np.concatenate([tone(0.1, 0.03), tone(0.3, 0.002), tone(1.0, 0.5)])

    trimmed, seconds = trim_lead(audio, SR, margin=0.08)

    assert seconds == pytest.approx(0.32, abs=0.04)
    assert len(trimmed) == len(audio) - int(round(seconds * SR))
    assert np.max(np.abs(trimmed[: int(0.05 * SR)])) < 0.01  # 留下的前導只是靜音


def test_nothing_is_trimmed_when_speech_starts_within_the_margin():
    audio = np.concatenate([silence(0.05), tone(1.0, 0.5)])

    trimmed, seconds = trim_lead(audio, SR, margin=0.08)

    assert seconds == 0.0 and len(trimmed) == len(audio)


def test_all_silent_or_empty_audio_is_left_alone():
    for audio in (silence(1.0), np.zeros(0, dtype=np.float32)):
        trimmed, seconds = trim_lead(audio, SR)
        assert seconds == 0.0 and len(trimmed) == len(audio)
