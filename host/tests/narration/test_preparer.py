import json
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


def make(tmp_path: Path, candidates, wiki=None, llm=None, speech=None, limit=2):
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
