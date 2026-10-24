import json
import wave

from buddy_host.places.models import Location
from buddy_host.tour.replay import ReplayPreparer


def write_fixture(directory, name, lat, lon, seconds=30.0):
    meta = {
        "candidate_id": f"wiki:{name}",
        "name": name,
        "lat": lat,
        "lon": lon,
        "script": f"{name}的稿子",
        "audio_seconds": seconds,
        "distance_m": 0,
    }
    (directory / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    (directory / f"{name}.wav").write_bytes(b"RIFF")


HERE = Location(25.0560, 121.5100)


async def test_returns_nearby_fixtures_nearest_first(tmp_path):
    write_fixture(tmp_path, "遠", 25.0600, 121.5100)  # 約 445 公尺
    write_fixture(tmp_path, "近", 25.0562, 121.5100)

    prepared = await ReplayPreparer(tmp_path).prepare(HERE)

    assert [p.name for p in prepared] == ["近", "遠"]
    assert prepared[0].wav_path == tmp_path / "近.wav"
    assert (prepared[0].lat, prepared[0].lon) == (25.0562, 121.5100)


async def test_skips_excluded_and_faraway_fixtures(tmp_path):
    write_fixture(tmp_path, "A", 25.0562, 121.5100)
    write_fixture(tmp_path, "很遠", 25.0372, 121.4999)

    prepared = await ReplayPreparer(tmp_path, radius_m=600).prepare(HERE, exclude_ids={"wiki:A"})

    assert prepared == []


async def test_limit_caps_the_number_of_narrations(tmp_path):
    for index in range(4):
        write_fixture(tmp_path, f"地點{index}", 25.0562 + index * 0.0001, 121.5100)

    prepared = await ReplayPreparer(tmp_path, limit=2).prepare(HERE)

    assert len(prepared) == 2


async def test_a_missing_directory_means_nothing_to_replay(tmp_path):
    assert await ReplayPreparer(tmp_path / "nope").prepare(HERE) == []


async def test_replays_narrations_stored_per_voice(tmp_path):
    """快取改成「稿子一份、音檔依聲音分開」之後，重播也要找得到音檔與秒數。"""
    meta = {
        "candidate_id": "wiki:新",
        "name": "新",
        "lat": 25.0562,
        "lon": 121.5100,
        "script": "新的稿子",
        "distance_m": 0,
    }
    (tmp_path / "新.meta.json").write_text(json.dumps(meta, ensure_ascii=False))
    voice_dir = tmp_path / "F2@1.2"
    voice_dir.mkdir()
    with wave.open(str(voice_dir / "新.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(1000)
        wav.writeframes(b"\0\0" * 2500)

    [found] = await ReplayPreparer(tmp_path).prepare(HERE)

    assert found.wav_path == voice_dir / "新.wav"
    assert found.audio_seconds == 2.5
