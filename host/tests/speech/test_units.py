import wave

import numpy as np

from buddy_host.speech.units import unit_starts

SR = 1000


def write(path, *pieces: tuple[str, float]) -> None:
    """('tone'｜'zero', 秒數) 依序接起來，存成 16-bit 單聲道 wav。"""
    parts = []
    for kind, seconds in pieces:
        n = int(SR * seconds)
        parts.append(np.full(n, 0.3 if kind == "tone" else 0.0, dtype=np.float32))
    pcm = (np.concatenate(parts) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())


def test_each_unit_starts_after_the_silence_the_pipeline_put_between_units(tmp_path):
    wav = tmp_path / "a.wav"
    write(wav, ("tone", 1.0), ("zero", 0.5), ("tone", 1.0), ("zero", 1.0), ("tone", 0.5))

    assert unit_starts(wav) == (0.0, 1.5, 3.5)


def test_a_short_silence_inside_a_unit_is_not_a_boundary(tmp_path):
    wav = tmp_path / "a.wav"
    write(wav, ("tone", 1.0), ("zero", 0.1), ("tone", 1.0))

    assert unit_starts(wav) == (0.0,)


def test_trailing_silence_does_not_make_a_unit(tmp_path):
    wav = tmp_path / "a.wav"
    write(wav, ("tone", 1.0), ("zero", 0.6))

    assert unit_starts(wav) == (0.0,)


def test_leading_silence_is_skipped(tmp_path):
    wav = tmp_path / "a.wav"
    write(wav, ("zero", 0.4), ("tone", 1.0), ("zero", 0.5), ("tone", 1.0))

    assert unit_starts(wav) == (0.4, 1.9)


def test_a_silent_or_missing_file_has_no_units(tmp_path):
    silent = tmp_path / "s.wav"
    write(silent, ("zero", 1.0))

    assert unit_starts(silent) == ()
    assert unit_starts(tmp_path / "missing.wav") == ()


def test_a_file_that_is_not_a_wav_has_no_units(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"not a wav")

    assert unit_starts(bad) == ()


def test_only_16_bit_mono_is_understood(tmp_path):
    stereo = tmp_path / "stereo.wav"
    with wave.open(str(stereo), "wb") as f:
        f.setnchannels(2)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((np.full(4000, 9000)).astype("<i2").tobytes())

    assert unit_starts(stereo) == ()
