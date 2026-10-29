import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from buddy_host.app import create_app
from buddy_host.config import HostConfig
from buddy_host.speech.phrases import PHRASES, voice_phrases_dir

TOKEN = {"X-Buddy-Token": "s3cret"}
CONTRACT = Path(__file__).parents[2] / "contract"


def make_client(home: Path, voice: str = "F2") -> TestClient:
    return TestClient(create_app(HostConfig(home=home, token="s3cret", voice=voice)))


def add_voice(home: Path, name: str, settings: str = "") -> Path:
    folder = home / "voice" / name
    folder.mkdir(parents=True)
    (folder / "voice.toml").write_text(settings, encoding="utf-8")
    return folder


def add_phrases(home: Path, key: str, numbers=tuple(PHRASES)) -> Path:
    folder = voice_phrases_dir(home, key)
    folder.mkdir(parents=True, exist_ok=True)
    for number in numbers:
        (folder / f"{number}.wav").write_bytes(f"RIFF {key} {number}".encode())
    return folder


def test_lists_the_voices_with_phrases_readiness_and_the_current_voice(tmp_path):
    add_voice(tmp_path, "F2", "speed = 1.2\ndisplay_name = '小晴'\ndescription = '女聲・溫暖'\n")
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
                "display_name": "小晴",
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

    (folder / "voice.toml").write_text("speed = 1.5\ndisplay_name = '小晴'\n", encoding="utf-8")
    voice = client.get("/v1/voices", headers=TOKEN).json()["voices"][0]

    assert voice["display_name"] == "小晴"
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
    add_voice(tmp_path, "F2", "speed = 1.2\ndisplay_name = '小晴'\ndescription = '女聲・溫暖'\n")
    add_voice(tmp_path, "M1", "speed = 1.2\ndisplay_name = '阿哲'\ndescription = '男聲・沉穩'\n")
    add_phrases(tmp_path, "F2@1.2")

    listed = make_client(tmp_path).get("/v1/voices", headers=TOKEN).json()

    assert listed == json.loads((CONTRACT / "voices.json").read_text(encoding="utf-8"))
