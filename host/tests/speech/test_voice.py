from pathlib import Path

import pytest

from buddy_host.speech.voice import VoiceError, list_voices, load_reference


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


def test_voice_without_settings_keeps_the_original_speed_and_pauses(tmp_path: Path):
    voice = load_reference(make_voice(tmp_path / "F2"))

    assert voice.name == "F2"
    assert voice.speed == 1.0
    assert voice.answer_max_pause_seconds is None


def test_settings_file_sets_speed_and_answer_pause_cap(tmp_path: Path):
    root = make_voice(tmp_path / "M1")
    (root / "voice.toml").write_text("speed = 1.2\nanswer_max_pause_seconds = 0.45\n")

    voice = load_reference(root)

    assert voice.speed == 1.2
    assert voice.answer_max_pause_seconds == 0.45


def test_voice_key_names_the_voice_and_its_speed(tmp_path: Path):
    plain = load_reference(make_voice(tmp_path / "F2"))
    root = make_voice(tmp_path / "M1")
    (root / "voice.toml").write_text("speed = 1.2\n")

    assert plain.key == "F2@1"
    assert load_reference(root).key == "M1@1.2"


@pytest.mark.parametrize(
    "settings, message",
    [
        ("speed = 0\n", "speed"),
        ("speed = 3.5\n", "speed"),
        ("speed = 'fast'\n", "speed"),
        ("answer_max_pause_seconds = 0\n", "answer_max_pause_seconds"),
        ("sped = 1.2\n", "sped"),
        ("speed = \n", "voice.toml"),
    ],
)
def test_bad_settings_are_a_clear_error(tmp_path: Path, settings, message):
    root = make_voice(tmp_path / "M1")
    (root / "voice.toml").write_text(settings)

    with pytest.raises(VoiceError, match=message):
        load_reference(root)


def test_default_voice_key_matches_the_default_voice_at_original_speed(tmp_path: Path):
    from buddy_host.narration.preparer import DEFAULT_VOICE_KEY

    assert load_reference(make_voice(tmp_path / "F2")).key == DEFAULT_VOICE_KEY


def test_settings_file_may_name_and_describe_the_voice(tmp_path: Path):
    root = make_voice(tmp_path / "F2")
    (root / "voice.toml").write_text("display_name = '示範女聲'\ndescription = '女聲・溫暖'\n")

    assert load_reference(root).key == "F2@1"  # 名稱與描述不影響合成


@pytest.mark.parametrize(
    "settings, message",
    [
        ("display_name = ''\n", "display_name"),
        ("display_name = 3\n", "display_name"),
        ("description = ['a']\n", "description"),
    ],
)
def test_bad_name_or_description_is_a_clear_error(tmp_path: Path, settings, message):
    root = make_voice(tmp_path / "F2")
    (root / "voice.toml").write_text(settings)

    with pytest.raises(VoiceError, match=message):
        load_reference(root)


def test_only_folders_with_voice_toml_are_listed(tmp_path: Path):
    (make_voice(tmp_path / "M1") / "voice.toml").write_text(
        "speed = 1.2\ndisplay_name = '示範男聲'\ndescription = '男聲・沉穩'\n"
    )
    (make_voice(tmp_path / "F2") / "voice.toml").write_text("")
    make_voice(tmp_path / "candidate")  # 篩選時留下的候選：沒有 voice.toml
    (tmp_path / "notes.txt").write_text("not a voice")

    voices = list_voices(tmp_path)

    assert [(v.name, v.display_name, v.description, v.key) for v in voices] == [
        ("F2", "F2", "", "F2@1"),  # 顯示名稱預設為資料夾名
        ("M1", "示範男聲", "男聲・沉穩", "M1@1.2"),
    ]


def test_a_broken_voice_toml_hides_only_that_voice(tmp_path: Path):
    (make_voice(tmp_path / "F2") / "voice.toml").write_text("speed = \n")  # 改到一半就存檔
    (make_voice(tmp_path / "M1") / "voice.toml").write_text("")

    assert [v.name for v in list_voices(tmp_path)] == ["M1"]


def test_no_voices_folder_lists_nothing(tmp_path: Path):
    assert list_voices(tmp_path / "voice") == []
