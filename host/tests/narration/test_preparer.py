import json
import shutil
from pathlib import Path

import numpy as np

from buddy_host.llm.models import LlmResult
from buddy_host.narration.preparer import AreaPreparer
from buddy_host.places.models import Candidate, Location
from buddy_host.places.wikipedia import WikiHit, WikiSummary
from buddy_host.speech.pipeline import SpeechResult

HERE = Location(25.0553, 121.5098, heading_deg=0.0)


def osm(name, north_m, wiki_title=None, **tags):
    return Candidate(
        f"osm:node:{name}",
        name,
        HERE.lat + north_m / 111_195,
        HERE.lon,
        {"tourism": "attraction", **tags},
        wiki_title=wiki_title,
    )


class FakeOverpass:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = 0

    async def nearby(self, box):
        self.calls += 1
        return self.candidates


class FakeWiki:
    def __init__(self, summaries=None, search=None, hits=()):
        self.summaries = summaries or {}
        self.search_map = search or {}
        self.hits = list(hits)

    async def geosearch(self, lat, lon, radius_m):
        return self.hits

    async def search(self, query):
        return self.search_map.get(query)

    async def summary(self, title):
        text = self.summaries.get(title)
        return WikiSummary(title, text, f"https://zh.wikipedia.org/wiki/{title}") if text else None


class FakeLlm:
    def __init__(self, text="你好，這是介紹稿。"):
        self.text = text
        self.requests = []

    async def run(self, request, on_text=None):
        self.requests.append(request)
        return LlmResult(self.text, "claude-sonnet-5-5", {}, {}, {}, 10)


class FakeSpeech:
    def __init__(self, seconds=3):
        self.texts = []
        self.seconds = seconds

    def run(self, text):
        self.texts.append(text)
        return SpeechResult(np.full(self.seconds * 1000, 0.1, dtype=np.float32), 1000, [], 0.5)


def make(tmp_path: Path, candidates, wiki=None, llm=None, speech=None, limit=2, voice_key=None):
    persona = tmp_path / "buddy.md"
    persona.write_text("你是小花。", encoding="utf-8")
    parts = dict(
        overpass=FakeOverpass(candidates),
        wiki=wiki or FakeWiki(),
        llm=llm or FakeLlm(),
        speech=speech or FakeSpeech(),
    )
    preparer = AreaPreparer(
        parts["overpass"],
        parts["wiki"],
        parts["llm"],
        parts["speech"],
        persona_path=persona,
        out_dir=tmp_path / "out",
        limit=limit,
        **({"voice_key": voice_key} if voice_key else {}),
    )
    return preparer, parts


async def test_prepares_the_top_ranked_places_with_audio_and_script(tmp_path):
    wiki = FakeWiki(summaries={"霞海城隍廟": "霞海城隍廟是大稻埕的廟宇。" * 10})
    cands = [osm("霞海城隍廟", 100, wiki_title="霞海城隍廟"), osm("普通景點", 300)]
    preparer, parts = make(tmp_path, cands, wiki)

    prepared = await preparer.prepare(HERE)

    assert [p.name for p in prepared] == ["霞海城隍廟", "普通景點"]
    first = prepared[0]
    assert first.wav_path.exists()
    assert first.audio_seconds == 3.0
    assert first.script == "你好，這是介紹稿。"
    assert parts["speech"].texts == ["你好，這是介紹稿。"] * 2
    assert (first.lat, first.lon) == (cands[0].lat, cands[0].lon)


async def test_cache_hit_keeps_the_place_coordinates(tmp_path):
    preparer, _ = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    first = await preparer.prepare(HERE)

    second = await preparer.prepare(HERE)

    assert (second[0].lat, second[0].lon) == (first[0].lat, first[0].lon)


async def test_prompt_gets_persona_wikipedia_facts_and_relative_direction(tmp_path):
    wiki = FakeWiki(summaries={"霞海城隍廟": "霞海城隍廟是大稻埕的廟宇。" * 10})
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100, wiki_title="霞海城隍廟")], wiki)

    await preparer.prepare(HERE)

    [request] = parts["llm"].requests
    assert request.system_prompt == "你是小花。"
    assert "大稻埕的廟宇" in request.prompt
    assert "前方" in request.prompt
    assert request.allowed_tools == ()


async def test_thin_facts_enable_web_tools(tmp_path):
    preparer, parts = make(tmp_path, [osm("無名小廟", 100)])

    await preparer.prepare(HERE)

    assert parts["llm"].requests[0].allowed_tools


async def test_wikipedia_search_fallback_requires_a_plausible_title(tmp_path):
    wiki = FakeWiki(
        summaries={"完全無關的條目": "不相干" * 40, "台北霞海城隍廟": "霞海城隍廟的介紹。" * 10},
        search={"霞海城隍廟": "台北霞海城隍廟", "迪化街": "完全無關的條目"},
    )
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100), osm("迪化街", 150)], wiki)

    await preparer.prepare(HERE)

    prompts = {r.prompt.split("」")[0]: r.prompt for r in parts["llm"].requests}
    assert any("霞海城隍廟的介紹" in p for p in prompts.values())
    assert not any("不相干" in p for p in prompts.values())


async def test_wikipedia_geosearch_hits_are_merged_into_the_candidates(tmp_path):
    wiki = FakeWiki(
        summaries={"迪化街": "迪化街的介紹。" * 20},
        hits=[WikiHit("迪化街", HERE.lat + 0.0008, HERE.lon)],
    )
    preparer, _ = make(tmp_path, [], wiki, limit=1)

    prepared = await preparer.prepare(HERE)

    assert [p.name for p in prepared] == ["迪化街"]


async def test_second_prepare_for_the_same_place_is_a_cache_hit(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)

    first = await preparer.prepare(HERE)
    second = await preparer.prepare(HERE)

    assert len(parts["llm"].requests) == 1
    assert second[0].script == first[0].script
    assert second[0].wav_path == first[0].wav_path


async def test_excluded_places_are_skipped(tmp_path):
    preparer, _ = make(tmp_path, [osm("A", 100), osm("B", 150)], limit=2)

    prepared = await preparer.prepare(HERE, exclude_ids={"osm:node:A"})

    assert [p.name for p in prepared] == ["B"]


async def test_empty_script_or_silent_speech_is_dropped(tmp_path):
    preparer, _ = make(tmp_path, [osm("A", 100)], llm=FakeLlm("   "))
    assert await preparer.prepare(HERE) == []

    (tmp_path / "b").mkdir()
    preparer, _ = make(tmp_path / "b", [osm("A", 100)], speech=FakeSpeech(seconds=0))
    assert await preparer.prepare(HERE) == []


async def test_meta_file_records_the_script_and_the_ranking(tmp_path):
    preparer, _ = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)

    [prepared] = await preparer.prepare(HERE)

    meta = json.loads(prepared.meta_path.read_text(encoding="utf-8"))
    assert meta["name"] == "霞海城隍廟"
    assert meta["script"] == "你好，這是介紹稿。"
    assert meta["candidate_id"] == "osm:node:霞海城隍廟"
    assert meta["distance_m"] > 0


async def test_scripts_are_written_concurrently_while_speech_is_synthesised_in_order(tmp_path):
    events: list[str] = []

    class LoggingLlm(FakeLlm):
        async def run(self, request, on_text=None):
            events.append("llm")
            return await super().run(request, on_text)

    class LoggingSpeech(FakeSpeech):
        def run(self, text):
            events.append("speech")
            return super().run(text)

    preparer, _ = make(
        tmp_path, [osm("A", 100), osm("B", 150)], llm=LoggingLlm(), speech=LoggingSpeech()
    )

    prepared = await preparer.prepare(HERE)

    assert events == ["llm", "llm", "speech", "speech"]
    assert [p.name for p in prepared] == ["A", "B"]


async def test_one_failing_script_does_not_lose_the_others(tmp_path):
    class FlakyLlm(FakeLlm):
        async def run(self, request, on_text=None):
            if "「A」" in request.prompt:
                raise RuntimeError("quota")
            return await super().run(request, on_text)

    preparer, _ = make(tmp_path, [osm("A", 100), osm("B", 150)], llm=FlakyLlm())

    prepared = await preparer.prepare(HERE)

    assert [p.name for p in prepared] == ["B"]


async def test_policy_and_quota_errors_stop_the_whole_preparation(tmp_path):
    import pytest

    from buddy_host.llm.claude_cli import QuotaExceededError
    from buddy_host.llm.models import ForbiddenModelError

    for error in (ForbiddenModelError("fable"), QuotaExceededError("limit")):

        class RaisingLlm(FakeLlm):
            async def run(self, request, on_text=None, _error=error):
                raise _error

        sub = tmp_path / type(error).__name__
        sub.mkdir()
        preparer, _ = make(sub, [osm("A", 100), osm("B", 150)], llm=RaisingLlm())

        with pytest.raises(type(error)):
            await preparer.prepare(HERE)


async def test_editing_the_persona_file_invalidates_cached_narrations(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    await preparer.prepare(HERE)

    (tmp_path / "buddy.md").write_text("你是小葉。", encoding="utf-8")
    await preparer.prepare(HERE)

    assert [r.system_prompt for r in parts["llm"].requests] == ["你是小花。", "你是小葉。"]


async def test_new_told_before_notes_invalidate_the_cache(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    await preparer.prepare(HERE)

    await preparer.prepare(HERE, told_before={"osm:node:霞海城隍廟": ("上次講過它是廟",)})

    assert len(parts["llm"].requests) == 2


async def test_nearby_positions_share_one_overpass_query(tmp_path):
    boxes = []

    class Recording(FakeOverpass):
        async def nearby(self, box):
            boxes.append(box)
            return []

    preparer, parts = make(tmp_path, [])
    preparer._overpass = Recording([])

    await preparer.prepare(Location(25.0553, 121.5098, 0.0))
    await preparer.prepare(Location(25.0551, 121.5101, 0.0))

    assert boxes[0] == boxes[1]


async def test_query_area_still_covers_the_search_radius_around_the_real_position(tmp_path):
    boxes = []

    class Recording(FakeOverpass):
        async def nearby(self, box):
            boxes.append(box)
            return []

    preparer, _ = make(tmp_path, [])
    preparer._overpass = Recording([])
    here = Location(25.0553, 121.5098, 0.0)

    await preparer.prepare(here)

    box = boxes[0]
    margin = 500 / 111_195
    assert box.min_lat <= here.lat - margin and box.max_lat >= here.lat + margin


class ScriptedLlm(FakeLlm):
    def __init__(self, *texts):
        super().__init__(texts[0])
        self.texts = list(texts)

    async def run(self, request, on_text=None):
        self.requests.append(request)
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return LlmResult(text, "claude-sonnet-5-5", {}, {}, {}, 10)


async def test_mainland_wording_triggers_one_rewrite_and_the_clean_version_is_used(tmp_path):
    llm = ScriptedLlm("我們看這個視頻。", "我們看這個影片。")
    preparer, _ = make(tmp_path, [osm("霞海城隍廟", 100)], llm=llm, limit=1)

    [prepared] = await preparer.prepare(HERE)

    assert len(llm.requests) == 2
    assert "視頻" in llm.requests[1].prompt
    assert prepared.script == "我們看這個影片。"
    assert json.loads(prepared.meta_path.read_text(encoding="utf-8"))["wording_issues"] == []


async def test_rewrites_are_capped_and_remaining_issues_are_recorded(tmp_path):
    llm = ScriptedLlm("我們看這個視頻。")
    preparer, _ = make(tmp_path, [osm("霞海城隍廟", 100)], llm=llm, limit=1)
    preparer._max_rewrites = 0

    [prepared] = await preparer.prepare(HERE)

    assert len(llm.requests) == 1  # 額度保護：不會自己多叫
    meta = json.loads(prepared.meta_path.read_text(encoding="utf-8"))
    assert meta["wording_issues"] == [{"term": "視頻", "suggestion": "影片"}]


async def test_clean_script_costs_a_single_call(tmp_path):
    llm = ScriptedLlm("我們搭捷運到大橋頭站。")
    preparer, _ = make(tmp_path, [osm("霞海城隍廟", 100)], llm=llm, limit=1)

    await preparer.prepare(HERE)

    assert len(llm.requests) == 1


async def test_traveler_state_reaches_the_prompt_and_invalidates_the_cache(tmp_path):
    from buddy_host.narration.traveler import Companions, TravelerContext

    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    await preparer.prepare(HERE)

    await preparer.prepare(HERE, traveler=TravelerContext(companions=Companions.FAMILY))
    await preparer.prepare(HERE, traveler=TravelerContext(companions=Companions.FAMILY))

    assert len(parts["llm"].requests) == 2  # 第三次與第二次狀態相同，用快取
    assert "家人" in parts["llm"].requests[1].prompt


async def test_on_ready_fires_for_each_narration_in_order_including_cache_hits(tmp_path):
    preparer, _ = make(tmp_path, [osm("A", 100), osm("B", 150)], limit=2)
    await preparer.prepare(HERE, exclude_ids={"osm:node:B"})  # 只有 A 進快取
    seen = []

    result = await preparer.prepare(HERE, on_ready=lambda item: seen.append(item.name))

    assert seen == ["A", "B"]
    assert [p.name for p in result] == seen


async def test_what_was_just_covered_reaches_the_prompt_and_invalidates_the_cache(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    await preparer.prepare(HERE)
    await preparer.prepare(HERE)
    assert len(parts["llm"].requests) == 1  # 同樣的狀況：快取命中

    await preparer.prepare(HERE, recent_topics=("龍山寺",))

    assert len(parts["llm"].requests) == 2  # 稿子會寫「剛剛的龍山寺」，不能沿用沒去過那裡的舊稿
    assert "龍山寺" in parts["llm"].requests[-1].prompt


async def test_the_journey_summary_in_the_prompt_stays_within_its_caps(tmp_path):
    from buddy_host.tour.journey import JourneyMemory

    journey = JourneyMemory(None, max_recent=3, told_per_place=2, told_chars=40)
    for index in range(30):  # 很長的一趟：三十個地方
        journey.begin(1000.0 + index * 100_000)
        journey.record_told(1000.0 + index * 100_000 + 1, f"p{index}", f"地方{index}", "稿" * 500)
        journey.finish(1000.0 + index * 100_000 + 2)
    journey.begin(5_000_000.0)
    for index in range(10):
        journey.record_told(5_000_001.0 + index, f"q{index}", f"站{index}", "稿" * 500)
    candidate = osm("霞海城隍廟", 100)
    for index in range(5):  # 這個地方以前講過很多次
        journey.begin(9_000_000.0 + index * 100_000)
        journey.record_told(
            9_000_001.0 + index * 100_000, candidate.id, candidate.name, f"第{index}次" + "字" * 500
        )
        journey.finish(9_000_002.0 + index * 100_000)
    journey.begin(20_000_000.0)
    preparer, parts = make(tmp_path, [candidate], limit=1)

    await preparer.prepare(
        HERE, recent_topics=journey.recent_topics(), told_before=journey.told_before()
    )

    prompt = parts["llm"].requests[0].prompt
    told_lines = [line for line in prompt.splitlines() if line.startswith("- 第")]
    assert len(told_lines) == 2  # 每個地方最多帶最近兩次
    assert all(len(line) <= 2 + 40 for line in told_lines)
    assert "地方0" not in prompt and "p0" not in prompt  # 以前別的地方不帶
    assert len(prompt) < 2000


async def test_nearby_describes_places_without_calling_claude_or_the_speech_engine(tmp_path):
    wiki = FakeWiki(summaries={"霞海城隍廟": "霞海城隍廟是大稻埕的廟宇。"})
    cands = [osm("霞海城隍廟", 100, wiki_title="霞海城隍廟"), osm("普通景點", 300)]
    preparer, parts = make(tmp_path, cands, wiki)

    places = await preparer.nearby(HERE, limit=5)

    assert [p.candidate.name for p in places] == ["霞海城隍廟", "普通景點"]
    first, second = places
    assert first.wiki_extract == "霞海城隍廟是大稻埕的廟宇。"
    assert second.wiki_extract is None
    assert 90 < first.distance_m < 110
    assert first.bearing_relative_deg == 0  # 正前方（朝北、景點在正北）
    assert parts["llm"].requests == [] and parts["speech"].texts == []


async def test_nearby_respects_the_limit_and_does_not_hide_places_already_told(tmp_path):
    cands = [osm("A", 100), osm("B", 200), osm("C", 300)]
    preparer, _ = make(tmp_path, cands)

    places = await preparer.nearby(HERE, limit=2)

    assert [p.candidate.name for p in places] == ["A", "B"]


async def test_nearby_queries_the_same_snapped_area_as_preparation(tmp_path):
    preparer, parts = make(tmp_path, [osm("A", 100)])
    boxes = []
    original = parts["overpass"].nearby

    async def recording(box):
        boxes.append(box)
        return await original(box)

    parts["overpass"].nearby = recording

    await preparer.nearby(HERE, limit=3)
    await preparer.prepare(Location(HERE.lat + 0.0001, HERE.lon, 0.0))  # 同一格內的另一點

    # 問答與主動介紹查同一個範圍，Overpass／維基的快取才共用
    assert len(boxes) == 2 and boxes[0] == boxes[1]


async def test_switching_voices_resynthesises_the_cached_script_without_claude(tmp_path):
    first, _ = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    [old] = await first.prepare(HERE)

    switched, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="M1@1.2")
    [new] = await switched.prepare(HERE)

    assert parts["llm"].requests == []
    assert parts["speech"].texts == [old.script]
    assert new.script == old.script
    assert new.wav_path != old.wav_path
    assert new.wav_path.parent.name == "M1@1.2"


async def test_the_script_is_stored_once_per_place_and_the_audio_once_per_voice(tmp_path):
    [a] = await make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="F2@1.2")[0].prepare(
        HERE
    )
    [b] = await make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="M1@1.2")[0].prepare(
        HERE
    )

    out = tmp_path / "out"
    assert a.meta_path == b.meta_path == out / "osm_node_霞海城隍廟.meta.json"
    assert a.wav_path == out / "F2@1.2" / "osm_node_霞海城隍廟.wav"
    assert b.wav_path == out / "M1@1.2" / "osm_node_霞海城隍廟.wav"
    assert a.wav_path.exists() and b.wav_path.exists()  # 兩個聲音的音檔並存
    assert a.wav_path.with_suffix(".log.json").exists()  # 合成紀錄跟著音檔
    meta = json.loads(a.meta_path.read_text(encoding="utf-8"))
    assert meta["script"] == "你好，這是介紹稿。"
    assert "voice" not in meta and "audio_seconds" not in meta  # 稿子與聲音無關


async def test_after_resynthesis_the_new_voice_is_a_plain_cache_hit(tmp_path):
    await make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)[0].prepare(HERE)
    await make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="M1@1.2")[0].prepare(HERE)

    again, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="M1@1.2")
    [hit] = await again.prepare(HERE)

    assert parts["llm"].requests == []
    assert parts["speech"].texts == []
    assert hit.audio_seconds == 3.0  # 秒數從音檔讀，不靠與聲音無關的 meta


async def test_switching_back_to_an_earlier_voice_hits_its_audio(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="F2@1.2")
    [first] = await preparer.prepare(HERE)
    preparer.voice_key = "M1@1.2"
    await preparer.prepare(HERE)
    parts["speech"].texts.clear()

    preparer.voice_key = "F2@1.2"
    [back] = await preparer.prepare(HERE)

    assert back.wav_path == first.wav_path
    assert parts["speech"].texts == []
    assert len(parts["llm"].requests) == 1  # 全程只寫過一次稿


async def test_the_voice_key_can_change_while_running(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    await preparer.prepare(HERE)

    preparer.voice_key = "M1@1.2"
    [new] = await preparer.prepare(HERE)

    assert parts["llm"].requests and len(parts["llm"].requests) == 1
    assert parts["speech"].texts == ["你好，這是介紹稿。"] * 2  # 兩個聲音各合成一次
    assert new.wav_path.parent.name == "M1@1.2"


async def test_a_prepare_files_its_audio_under_the_voice_it_started_with(tmp_path):
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="F2@1.2")
    original_run = parts["speech"].run

    def switch_during_synthesis(text):
        preparer.voice_key = "M1@1.2"  # 合成到一半，使用者換了聲音
        return original_run(text)

    parts["speech"].run = switch_during_synthesis

    [made] = await preparer.prepare(HERE)

    assert made.wav_path.parent.name == "F2@1.2"
    assert not (tmp_path / "out" / "M1@1.2").exists()


def write_legacy_cache(out, script="舊的稿子。", fingerprint=None):
    """聲音可設定之前的平放格式：音檔與 meta 同一層，meta 裡有 voice、audio_seconds。"""
    out.mkdir(parents=True, exist_ok=True)
    (out / "osm_node_霞海城隍廟.wav").write_bytes(b"RIFF-old")
    meta = {
        "candidate_id": "osm:node:霞海城隍廟",
        "name": "霞海城隍廟",
        "lat": HERE.lat,
        "lon": HERE.lon,
        "distance_m": 100.0,
        "script": script,
        "fingerprint": fingerprint,
        "voice": "F2@1",
        "audio_seconds": 99.0,
    }
    (out / "osm_node_霞海城隍廟.meta.json").write_text(json.dumps(meta, ensure_ascii=False))


async def test_old_flat_audio_is_not_used_but_its_script_is_resynthesised(tmp_path):
    seeded, _ = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    [made] = await seeded.prepare(HERE)  # 先取得目前的指紋
    fingerprint = json.loads(made.meta_path.read_text(encoding="utf-8"))["fingerprint"]
    shutil.rmtree(tmp_path / "out")
    write_legacy_cache(tmp_path / "out", fingerprint=fingerprint)

    again, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)
    [fresh] = await again.prepare(HERE)

    assert parts["llm"].requests == []  # 稿子在快取裡：不呼叫 Claude
    assert parts["speech"].texts == ["舊的稿子。"]  # 從稿子以目前聲音重新合成
    assert fresh.wav_path != tmp_path / "out" / "osm_node_霞海城隍廟.wav"
    assert fresh.audio_seconds == 3.0  # 不是舊 meta 裡的 99


async def test_a_new_script_is_still_written_when_the_place_changed_its_fingerprint(tmp_path):
    await make(tmp_path, [osm("霞海城隍廟", 100)], limit=1)[0].prepare(HERE)

    switched, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="M1@1.2")
    (tmp_path / "buddy.md").write_text("你是小草。", encoding="utf-8")  # 個性檔改了：舊稿不能用
    await switched.prepare(HERE)

    assert len(parts["llm"].requests) == 1


async def test_audio_made_from_an_old_script_is_not_reused_after_the_script_is_rewritten(tmp_path):
    """指紋變了、稿子重寫之後，別的聲音底下用舊稿合成的音檔不能再被當成命中。"""
    preparer, parts = make(tmp_path, [osm("霞海城隍廟", 100)], limit=1, voice_key="F2@1.2")
    await preparer.prepare(HERE)
    preparer.voice_key = "M1@1.2"
    await preparer.prepare(HERE)
    (tmp_path / "buddy.md").write_text("你是小草。", encoding="utf-8")  # 個性檔改了：要重寫稿
    parts["llm"].text = "全新的稿子。"
    await preparer.prepare(HERE)  # M1 底下用新稿重新合成

    parts["speech"].texts.clear()
    preparer.voice_key = "F2@1.2"
    [back] = await preparer.prepare(HERE)

    assert back.script == "全新的稿子。"
    assert parts["speech"].texts == ["全新的稿子。"]  # F2 的舊音檔作廢，用新稿重合成
    assert len(parts["llm"].requests) == 2  # 切回 F2 沒有再寫稿
