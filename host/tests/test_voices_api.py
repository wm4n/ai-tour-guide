import dataclasses
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from buddy_host.app import create_app
from buddy_host.config import HostConfig
from buddy_host.narration.preparer import PreparedNarration
from buddy_host.speech.phrases import PHRASES, voice_phrases_dir
from buddy_host.speech.voice import read_current_voice

TOKEN = {"X-Buddy-Token": "s3cret"}
CONTRACT = Path(__file__).parents[2] / "contract"
F2_TOML = "speed = 1.2\ndisplay_name = '示範女聲'\ndescription = '女聲・溫暖'\n"
M1_TOML = "speed = 1.2\ndisplay_name = '示範男聲'\ndescription = '男聲・沉穩'\n"


def make_client(home: Path, voice: str = "F2", on_voice_change=None, preparer=None) -> TestClient:
    config = HostConfig(home=home, token="s3cret", voice=voice)
    return TestClient(create_app(config, preparer, on_voice_change=on_voice_change))


def add_voice(home: Path, name: str, settings: str = "") -> Path:
    folder = home / "voice" / name
    folder.mkdir(parents=True)
    (folder / "voice.toml").write_text(settings, encoding="utf-8")
    return folder


def add_usable_voice(home: Path, name: str, numbers=tuple(PHRASES)) -> Path:
    """可以拿來合成的聲音：有參考錄音、逐字稿、voice.toml（1.2 倍），以及 [numbers] 這幾句短句。"""
    folder = add_voice(home, name, "speed = 1.2\n")
    (folder / "ref_24k.wav").write_bytes(b"RIFF")
    (folder / "ref_text.txt").write_text("參考逐字稿。", encoding="utf-8")
    add_phrases(home, f"{name}@1.2", numbers=numbers)
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
    add_usable_voice(tmp_path, "M1", numbers=[1, 2])
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


class TwoPlacesPreparer:
    """出發就準備好 A、B 兩段；重做時換成目前的聲音。"""

    def __init__(self, wav: Path):
        self.wav = wav
        self.voice_key = "F2@1.2"
        self.revoiced: list[list[str]] = []

    def _item(self, name: str) -> PreparedNarration:
        return PreparedNarration(
            f"wiki:{name}", name, "稿", self.wav, self.wav, 30.0, 50.0, 25.05, 121.51,
            self.voice_key,
        )  # fmt: skip

    async def prepare(self, location, **_):
        return [self._item("A"), self._item("B")]

    async def revoice(self, narrations, *, on_ready=None):
        self.revoiced.append([item.candidate_id for item in narrations])
        redone = [dataclasses.replace(item, voice=self.voice_key) for item in narrations]
        for item in redone:
            if on_ready:
                on_ready(item)
        return redone


def narrations_once(client: TestClient, count: int) -> dict:
    for _ in range(100):
        body = client.get("/v1/tour/narrations", headers=TOKEN).json()
        if len(body["narrations"]) >= count:
            return body
        time.sleep(0.02)
    raise AssertionError(f"沒有等到 {count} 段介紹：{body}")


def test_switching_during_a_tour_redoes_what_has_not_played_in_the_new_voice(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    preparer = TwoPlacesPreparer(wav)
    changed = []
    with make_client(tmp_path, on_voice_change=changed.append, preparer=preparer) as client:
        client.post("/v1/tour/start", json={"lat": 25.05, "lon": 121.51}, headers=TOKEN)
        narrations_once(client, 2)

        response = client.post(
            "/v1/voice", json={"name": "M1", "playing_id": "wiki:A"}, headers=TOKEN
        )
        body = narrations_once(client, 2)

    assert response.json() == {"current": "M1"}
    assert [voice.name for voice in changed] == ["M1"]
    assert preparer.revoiced == [["wiki:B"]]  # A 正在播、會播完：不丟
    assert body["voice"] == "M1@1.2"
    assert [(n["seq"], n["id"], n["voice"]) for n in body["narrations"]] == [
        (1, "wiki:A", "F2@1.2"),
        (3, "wiki:B", "M1@1.2"),
    ]


def test_what_the_app_already_played_is_told_before_the_rest_is_withdrawn(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    preparer = TwoPlacesPreparer(wav)
    with make_client(tmp_path, preparer=preparer) as client:
        client.post("/v1/tour/start", json={"lat": 25.05, "lon": 121.51}, headers=TOKEN)
        narrations_once(client, 2)

        # A 播完了但回報還沒送到；B 被問題打斷、等著接續
        response = client.post(
            "/v1/voice", json={"name": "M1", "played_ids": ["wiki:A", "wiki:B"]}, headers=TOKEN
        )
        body = narrations_once(client, 2)

    assert response.status_code == 200
    assert preparer.revoiced == []  # 都講過了：不用新聲音重講
    assert [(n["id"], n["voice"]) for n in body["narrations"]] == [
        ("wiki:A", "F2@1.2"),
        ("wiki:B", "F2@1.2"),
    ]


def test_played_ids_are_told_even_when_the_voice_stays_the_same(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"RIFF")
    preparer = TwoPlacesPreparer(wav)
    with make_client(tmp_path, preparer=preparer) as client:
        client.post("/v1/tour/start", json={"lat": 25.05, "lon": 121.51}, headers=TOKEN)
        narrations_once(client, 2)

        # 切換中又點回原本的聲音：App 收到 200 就清掉待送回報，主機不能漏記
        client.post("/v1/voice", json={"name": "F2", "played_ids": ["wiki:A"]}, headers=TOKEN)
        client.post("/v1/voice", json={"name": "M1"}, headers=TOKEN)
        narrations_once(client, 2)

    assert preparer.revoiced == [["wiki:B"]]


def test_played_ids_the_host_does_not_know_are_ignored(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")
    with make_client(tmp_path, preparer=TwoPlacesPreparer(tmp_path / "a.wav")) as client:
        response = client.post(
            "/v1/voice", json={"name": "M1", "played_ids": ["wiki:重啟之前的"]}, headers=TOKEN
        )

    assert response.json() == {"current": "M1"}


def test_switching_without_a_tour_changes_the_voice_of_the_next_narrations(tmp_path):
    add_usable_voice(tmp_path, "F2")
    add_usable_voice(tmp_path, "M1")
    preparer = TwoPlacesPreparer(tmp_path / "a.wav")
    with make_client(tmp_path, preparer=preparer) as client:
        client.post("/v1/voice", json={"name": "M1"}, headers=TOKEN)

        assert client.get("/v1/tour/narrations", headers=TOKEN).json()["voice"] == "M1@1.2"
    assert preparer.revoiced == []


def test_the_narrations_start_in_the_voice_the_host_started_with(tmp_path):
    add_usable_voice(tmp_path, "F2")
    preparer = TwoPlacesPreparer(tmp_path / "a.wav")
    preparer.voice_key = "F2@1.2"  # 主機啟動時用目前聲音建好準備器

    with make_client(tmp_path, preparer=preparer) as client:
        assert client.get("/v1/tour/narrations", headers=TOKEN).json()["voice"] == "F2@1.2"
