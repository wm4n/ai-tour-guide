import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from buddy_host.app import create_app
from buddy_host.config import HostConfig
from buddy_host.speech.phrases import PHRASES, voice_phrases_dir
from buddy_host.speech.voice import read_current_voice

TOKEN = {"X-Buddy-Token": "s3cret"}
CONTRACT = Path(__file__).parents[2] / "contract"
F2_TOML = "speed = 1.2\ndisplay_name = '示範女聲'\ndescription = '女聲・溫暖'\n"
M1_TOML = "speed = 1.2\ndisplay_name = '示範男聲'\ndescription = '男聲・沉穩'\n"


def make_client(home: Path, voice: str = "F2", on_voice_change=None) -> TestClient:
    config = HostConfig(home=home, token="s3cret", voice=voice)
    return TestClient(create_app(config, on_voice_change=on_voice_change))


def add_voice(home: Path, name: str, settings: str = "") -> Path:
    folder = home / "voice" / name
    folder.mkdir(parents=True)
    (folder / "voice.toml").write_text(settings, encoding="utf-8")
    return folder


def add_usable_voice(home: Path, name: str, settings: str = "speed = 1.2\n") -> Path:
    """可以拿來合成的聲音：有參考錄音、逐字稿、voice.toml，短句也都準備好了。"""
    folder = add_voice(home, name, settings)
    (folder / "ref_24k.wav").write_bytes(b"RIFF")
    (folder / "ref_text.txt").write_text("參考逐字稿。", encoding="utf-8")
    add_phrases(home, f"{name}@1.2")
    return folder


def add_phrases(home: Path, key: str, numbers=tuple(PHRASES)) -> Path:
    folder = voice_phrases_dir(home, key)
    folder.mkdir(parents=True, exist_ok=True)
    for number in numbers:
        (folder / f"{number}.wav").write_bytes(f"RIFF {key} {number}".encode())
    return folder


def test_lists_the_voices_with_phrases_readiness_and_the_current_voice(tmp_path):
    add_voice(tmp_path, "F2", F2_TOML)
    add_voice(tmp_path, "M1", "speed = 1.2\n")
    (tmp_path / "voice" / "candidate").mkdir()  # 沒有 voice.toml：不列出
    add_phrases(tmp_path, "F2@1.2")
    add_phrases(tmp_path, "M1@1.2", numbers=[1, 2])  # 還差幾句

    response = make_client(tmp_path).get("/v1/voices", headers=TOKEN)

    assert response.status_code == 200
    assert response.json() == {
        "current": "F2",
        "voices": [
            {
                "name": "F2",
                "display_name": "示範女聲",
                "description": "女聲・溫暖",
                "key": "F2@1.2",
                "phrases_ready": True,
            },
            {
                "name": "M1",
                "display_name": "M1",
                "description": "",
                "key": "M1@1.2",
                "phrases_ready": False,
            },
        ],
    }


def test_edits_to_voice_toml_show_up_without_a_restart(tmp_path):
    folder = add_voice(tmp_path, "F2", "speed = 1.2\n")
    add_phrases(tmp_path, "F2@1.2")
    client = make_client(tmp_path)
    assert client.get("/v1/voices", headers=TOKEN).json()["voices"][0]["phrases_ready"] is True

    (folder / "voice.toml").write_text("speed = 1.5\ndisplay_name = '示範女聲'\n", encoding="utf-8")
    voice = client.get("/v1/voices", headers=TOKEN).json()["voices"][0]

    assert voice["display_name"] == "示範女聲"
    assert voice["key"] == "F2@1.5"
    assert voice["phrases_ready"] is False  # 改了語速：短句要重新產生


def test_downloads_a_phrase_of_a_voice_at_its_current_speed(tmp_path):
    add_voice(tmp_path, "M1", "speed = 1.2\n")
    add_phrases(tmp_path, "M1@1.2")

    response = make_client(tmp_path).get("/v1/voices/M1/phrases/7", headers=TOKEN)

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"RIFF M1@1.2 7"


@pytest.mark.parametrize(
    "path",
    [
        "/v1/voices/M1/phrases/4",  # 這句還沒產生
        "/v1/voices/M1/phrases/5",  # 不是固定短句的編號
        "/v1/voices/nobody/phrases/7",  # 沒有這個聲音
        "/v1/voices/candidate/phrases/7",  # 沒有 voice.toml 的資料夾不算聲音
        "/v1/voices/..%2Fvoice-phrases/phrases/7",
    ],
)
def test_missing_phrases_are_404_without_leaking_paths(tmp_path, path):
    add_voice(tmp_path, "M1", "speed = 1.2\n")
    add_phrases(tmp_path, "M1@1.2", numbers=[7])
    (tmp_path / "out" / "voice-phrases" / "5.wav").write_bytes(b"RIFF")
    candidate = tmp_path / "voice" / "candidate"
    candidate.mkdir()
    add_phrases(tmp_path, "candidate@1")

    response = make_client(tmp_path).get(path, headers=TOKEN)

    assert response.status_code == 404
    assert str(tmp_path) not in response.text


@pytest.mark.parametrize("path", ["/v1/voices", "/v1/voices/M1/phrases/7"])
def test_voice_endpoints_require_the_token(tmp_path, path):
    add_voice(tmp_path, "M1")
    add_phrases(tmp_path, "M1@1")

    assert make_client(tmp_path).get(path).status_code == 401


def test_the_voice_list_matches_the_contract_the_app_is_tested_against(tmp_path):
    add_voice(tmp_path, "F2", F2_TOML)
    add_voice(tmp_path, "M1", M1_TOML)
    add_phrases(tmp_path, "F2@1.2")

    listed = make_client(tmp_path).get("/v1/voices", headers=TOKEN).json()

    assert listed == json.loads((CONTRACT / "voices.json").read_text(encoding="utf-8"))


def test_switching_voice_hands_the_reloaded_voice_to_the_synthesizer(tmp_path):
    add_usable_voice(tmp_path, "F2")
    folder = add_usable_voice(tmp_path, "M1")
    changed = []
    client = make_client(tmp_path, on_voice_change=changed.append)
    # 切換時重讀 voice.toml：主機開著時改的語速與停頓上限也要套用
    (folder / "voice.toml").write_text(
        "speed = 1.2\nanswer_max_pause_seconds = 0.3\n", encoding="utf-8"
    )

    response = client.post("/v1/voice", json={"name": "M1"}, headers=TOKEN)

    assert response.status_code == 200
    assert response.json() == {"current": "M1"}
    [voice] = changed
    assert (voice.name, voice.key, voice.answer_max_pause_seconds) == ("M1", "M1@1.2", 0.3)
    assert client.get("/v1/voices", headers=TOKEN).json()["current"] == "M1"


def test_the_choice_is_saved_for_the_next_start(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")

    make_client(tmp_path).post("/v1/voice", json={"name": "M1"}, headers=TOKEN)

    assert read_current_voice(tmp_path, "F2") == "M1"


def test_switching_to_the_current_voice_does_nothing(tmp_path):
    add_usable_voice(tmp_path, "F2")
    changed = []

    response = make_client(tmp_path, on_voice_change=changed.append).post(
        "/v1/voice", json={"name": "F2"}, headers=TOKEN
    )

    assert response.status_code == 200
    assert response.json() == {"current": "F2"}
    assert changed == []
    assert not (tmp_path / "voice" / "current").exists()


def test_the_last_of_several_switches_wins(tmp_path):
    for name in ("F2", "M1", "M2"):
        add_usable_voice(tmp_path, name)
    changed = []
    client = make_client(tmp_path, on_voice_change=changed.append)

    client.post("/v1/voice", json={"name": "M1"}, headers=TOKEN)
    client.post("/v1/voice", json={"name": "M2"}, headers=TOKEN)

    assert [voice.name for voice in changed] == ["M1", "M2"]
    assert read_current_voice(tmp_path, "F2") == "M2"


def test_switching_without_a_synthesizer_still_records_the_choice(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")
    client = make_client(tmp_path)  # 重播模式：沒有合成器

    assert client.post("/v1/voice", json={"name": "M1"}, headers=TOKEN).status_code == 200
    assert client.get("/v1/voices", headers=TOKEN).json()["current"] == "M1"


def test_an_unknown_voice_is_404(tmp_path):
    add_usable_voice(tmp_path, "F2")
    (tmp_path / "voice" / "candidate").mkdir()  # 沒有 voice.toml 的資料夾不算聲音

    for name in ("nobody", "candidate", ".."):
        response = make_client(tmp_path).post("/v1/voice", json={"name": name}, headers=TOKEN)
        assert response.status_code == 404


def test_a_voice_without_phrases_cannot_be_chosen(tmp_path):
    add_usable_voice(tmp_path, "F2")
    folder = add_voice(tmp_path, "M1", "speed = 1.2\n")
    (folder / "ref_24k.wav").write_bytes(b"RIFF")
    (folder / "ref_text.txt").write_text("參考逐字稿。", encoding="utf-8")
    add_phrases(tmp_path, "M1@1.2", numbers=[1, 2])
    changed = []

    response = make_client(tmp_path, on_voice_change=changed.append).post(
        "/v1/voice", json={"name": "M1"}, headers=TOKEN
    )

    assert response.status_code == 409
    assert changed == []
    assert not (tmp_path / "voice" / "current").exists()


def test_a_voice_missing_its_reference_recording_cannot_be_chosen(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_voice(tmp_path, "M1", "speed = 1.2\n")  # 有 voice.toml、短句，但沒有參考錄音
    add_phrases(tmp_path, "M1@1.2")

    response = make_client(tmp_path).post("/v1/voice", json={"name": "M1"}, headers=TOKEN)

    assert response.status_code == 409
    assert str(tmp_path) not in response.text


def test_switching_requires_the_token(tmp_path):
    add_usable_voice(tmp_path, "M1")

    assert make_client(tmp_path).post("/v1/voice", json={"name": "M1"}).status_code == 401


def test_the_switch_response_matches_the_contract_the_app_is_tested_against(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")

    response = make_client(tmp_path).post("/v1/voice", json={"name": "M1"}, headers=TOKEN)

    assert response.json() == json.loads((CONTRACT / "voice-switch.json").read_text("utf-8"))
