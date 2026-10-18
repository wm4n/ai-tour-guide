from pathlib import Path

import pytest

from buddy_host.speech.voice import VoiceError, load_reference


def make_voice(root: Path, *, wav: bool = True, text: str | None = "你好，這是參考聲音。") -> Path:
    root.mkdir(parents=True)
    if wav:
        (root / "ref_24k.wav").write_bytes(b"RIFF")
    if text is not None:
        (root / "ref_text.txt").write_text(text + "\n", encoding="utf-8")
    return root


def test_loads_wav_path_and_stripped_transcript(tmp_path: Path):
    voice = load_reference(make_voice(tmp_path / "F2"))

    assert voice.wav_path == tmp_path / "F2" / "ref_24k.wav"
    assert voice.text == "你好，這是參考聲音。"


def test_missing_directory_is_a_clear_error(tmp_path: Path):
    with pytest.raises(VoiceError, match="找不到參考聲音"):
        load_reference(tmp_path / "nope")


def test_missing_wav(tmp_path: Path):
    with pytest.raises(VoiceError, match="ref_24k.wav"):
        load_reference(make_voice(tmp_path / "F2", wav=False))


@pytest.mark.parametrize("text", [None, "", "   \n"])
def test_reference_text_is_mandatory(tmp_path: Path, text):
    with pytest.raises(VoiceError, match="reference_text"):
        load_reference(make_voice(tmp_path / "F2", text=text))
