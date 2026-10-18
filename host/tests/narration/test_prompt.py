from pathlib import Path

from buddy_host.llm.models import Purpose
from buddy_host.narration.prompt import (
    WEB_TOOLS,
    ScriptContext,
    build_script_request,
    describe_direction,
    load_persona,
)
from buddy_host.places.models import Candidate

LONG = "迪化街是台北市大稻埕的一條老街，清末起就是南北貨與中藥材的集散地。" * 4


def ctx(**kw) -> ScriptContext:
    base = dict(
        candidate=Candidate(
            "osm:node:1",
            "霞海城隍廟",
            25.0554,
            121.5099,
            {"amenity": "place_of_worship", "start_date": "1859"},
        ),
        wiki_extract=LONG,
        distance_m=120.0,
        bearing_relative_deg=10.0,
        told_before=(),
        recent_topics=(),
    )
    base.update(kw)
    return ScriptContext(**base)


def test_persona_is_re_read_on_every_call(tmp_path: Path):
    path = tmp_path / "buddy.md"
    path.write_text("你是小花。", encoding="utf-8")
    assert load_persona(path) == "你是小花。"

    path.write_text("你是小葉。", encoding="utf-8")

    assert load_persona(path) == "你是小葉。"


def test_request_uses_persona_as_system_prompt_and_the_write_purpose():
    request = build_script_request("你是小花。", ctx())

    assert request.system_prompt == "你是小花。"
    assert request.purpose is Purpose.WRITE


def test_prompt_contains_name_facts_and_position():
    request = build_script_request("p", ctx())

    assert "霞海城隍廟" in request.prompt
    assert "迪化街是台北市" in request.prompt
    assert "start_date" in request.prompt or "1859" in request.prompt
    assert "前方" in request.prompt
    assert "120" in request.prompt


def test_prompt_asks_for_plain_speech_text_of_the_configured_length():
    request = build_script_request("p", ctx(), seconds=(30, 45))

    assert "30" in request.prompt and "45" in request.prompt
    assert "只輸出" in request.prompt


def test_previously_told_places_ask_for_a_new_angle():
    request = build_script_request("p", ctx(told_before=("上次講過它是廟宇與祭典",)))

    assert "講過" in request.prompt
    assert "上次講過它是廟宇與祭典" in request.prompt
    assert "換個角度" in request.prompt


def test_recent_topics_are_listed_for_contrast():
    request = build_script_request("p", ctx(recent_topics=("迪化街茶行", "大稻埕碼頭")))

    assert "迪化街茶行" in request.prompt and "大稻埕碼頭" in request.prompt


def test_web_tools_are_only_enabled_when_the_facts_are_thin():
    thin = build_script_request("p", ctx(wiki_extract=None))
    rich = build_script_request("p", ctx())

    assert thin.allowed_tools == WEB_TOOLS
    assert "上網" in thin.prompt
    assert rich.allowed_tools == ()
    assert "上網" not in rich.prompt


def test_model_can_be_overridden():
    assert build_script_request("p", ctx(), model="haiku").model == "haiku"


def test_describe_direction():
    assert describe_direction(0) == "正前方"
    assert describe_direction(45) == "右前方"
    assert describe_direction(-45) == "左前方"
    assert describe_direction(90) == "右手邊"
    assert describe_direction(-90) == "左手邊"
    assert describe_direction(180) == "後方"
    assert describe_direction(None) == "附近"
