import numpy as np
import pytest

from buddy_host.speech.pauses import cap_pauses

SR = 24_000
EDGE = 1024 / SR  # 偵測的解析度：每個說話邊界最多偏一個音框（音框以中心為準，邊界會略往外擴）


def tone(seconds: float, amplitude: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * SR)) / SR
    return (amplitude * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SR), dtype=np.float32)


def seconds(audio: np.ndarray) -> float:
    return len(audio) / SR


def test_long_pause_between_words_is_shortened_to_the_cap():
    audio = np.concatenate([tone(1.0), silence(2.0), tone(1.0)])

    out = cap_pauses(audio, SR, 0.45)

    assert seconds(out) == pytest.approx(2.45, abs=2 * EDGE)


def test_pause_shorter_than_the_cap_is_left_alone():
    audio = np.concatenate([tone(1.0), silence(0.3), tone(1.0)])

    out = cap_pauses(audio, SR, 0.45)

    assert np.array_equal(out, audio)


def test_every_long_pause_is_capped():
    audio = np.concatenate([tone(0.5), silence(1.0), tone(0.5), silence(1.5), tone(0.5)])

    out = cap_pauses(audio, SR, 0.45)

    assert seconds(out) == pytest.approx(1.5 + 2 * 0.45, abs=4 * EDGE)


def test_leading_and_trailing_silence_keep_half_the_cap_each():
    audio = np.concatenate([silence(1.0), tone(1.0), silence(1.0)])

    out = cap_pauses(audio, SR, 0.45)

    assert seconds(out) == pytest.approx(1.0 + 0.45, abs=2 * EDGE)


def test_speech_itself_is_untouched():
    first, second = tone(1.0), tone(0.8, amplitude=0.2)
    audio = np.concatenate([first, silence(2.0), second])

    out = cap_pauses(audio, SR, 0.45)

    assert np.array_equal(out[: len(first)], first)
    assert np.array_equal(out[-len(second) :], second)


def test_quiet_speech_is_not_mistaken_for_silence():
    audio = np.concatenate([tone(1.0), tone(1.0, amplitude=0.02), tone(1.0)])

    out = cap_pauses(audio, SR, 0.45)

    assert np.array_equal(out, audio)


@pytest.mark.parametrize("audio", [np.zeros(0, np.float32), silence(1.0)])
def test_empty_or_all_silent_audio_is_returned_as_is(audio):
    assert np.array_equal(cap_pauses(audio, SR, 0.45), audio)
