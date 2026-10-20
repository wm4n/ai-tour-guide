from pathlib import Path

from buddy_host.llm.models import Purpose, resolve_model
from buddy_host.narration.prompt import WEB_TOOLS, ScriptContext
from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode
from buddy_host.places.models import Candidate, Location
from buddy_host.qa.prompt import (
    QA_INSTRUCTIONS,
    AskContext,
    PhotoInput,
    build_answer_request,
    describe_compass,
)

PERSONA = "你是小花。"
HERE = Location(25.056, 121.51, heading_deg=200.0)


def place(name="霞海城隍廟", extract="霞海城隍廟是大稻埕的廟宇。", **kw) -> ScriptContext:
    return ScriptContext(
        candidate=Candidate(f"wiki:{name}", name, 25.0554, 121.5099, {"tourism": "attraction"}),
        wiki_extract=extract,
        distance_m=kw.pop("distance_m", 120.0),
        bearing_relative_deg=kw.pop("bearing_relative_deg", 10.0),
        **kw,
    )


def ask(**kw) -> AskContext:
    base = dict(question="那間廟拜的是誰？", location=HERE, traveler=None)
    base.update(kw)
    return AskContext(**base)


def build(**kw):
    return build_answer_request(PERSONA, ask(**kw))


def test_the_request_is_a_sonnet_qa_call_that_may_use_web_tools():
    request = build()

    assert request.purpose is Purpose.QA
    assert request.model == "sonnet"
    assert resolve_model(request.purpose, request.model) == "sonnet"
    assert request.allowed_tools == WEB_TOOLS


def test_the_system_prompt_is_the_persona_plus_qa_instructions():
    request = build()

    assert request.system_prompt.startswith(PERSONA)
    assert QA_INSTRUCTIONS in request.system_prompt


def test_the_prompt_carries_the_question_position_and_heading():
    prompt = build().prompt

    assert "那間廟拜的是誰？" in prompt
    assert "25.0560" in prompt and "121.5100" in prompt
    assert "正朝南" in prompt  # 行進方向 200 度


def test_without_a_heading_it_says_the_direction_is_unknown():
    prompt = build(location=Location(25.0, 121.5)).prompt

    assert "行進方向未知" in prompt


def test_compass_names():
    names = [describe_compass(d) for d in (0, 45, 90, 135, 180, 225, 270, 315, 359)]

    assert names == ["北", "東北", "東", "東南", "南", "西南", "西", "西北", "北"]


def test_traveler_state_is_included_when_known():
    traveler = TravelerContext(TravelMode.DRIVING, Companions.FAMILY, True)

    prompt = build(traveler=traveler).prompt

    assert "開車" in prompt and "家人" in prompt and "小朋友" in prompt


def test_nearby_places_carry_distance_direction_and_a_clipped_summary():
    long_extract = "很長的摘要。" * 100
    nearby = (place(extract=long_extract, distance_m=120, bearing_relative_deg=0),)

    prompt = build(nearby=nearby).prompt

    assert "霞海城隍廟" in prompt
    assert "正前方" in prompt and "120 公尺" in prompt
    assert long_extract not in prompt  # 摘要有長度上限
    assert "…" in prompt


def test_places_without_a_summary_are_still_listed():
    prompt = build(nearby=(place(extract=None),)).prompt

    assert "霞海城隍廟" in prompt and "（沒有）" in prompt


def test_the_journey_summary_comes_along():
    told = {"wiki:霞海城隍廟": ("上次講過它是茶行。",), "wiki:別處": ("無關",)}

    prompt = build(nearby=(place(),), recent_topics=("迪化街", "永樂市場"), told_before=told).prompt

    assert "迪化街、永樂市場" in prompt
    assert "上次講過它是茶行。" in prompt
    assert "無關" not in prompt  # 只帶附近景點的


def test_a_plain_question_does_not_mention_the_last_narration():
    prompt = build(last_told=("迪化街", "迪化街的稿子")).prompt

    assert "迪化街的稿子" not in prompt


def test_asking_for_more_hands_over_what_was_just_told():
    prompt = build(question="再多說一點", more=True, last_told=("迪化街", "迪化街的稿子")).prompt

    assert "迪化街" in prompt and "迪化街的稿子" in prompt
    assert "多聽一點" in prompt


def test_asking_for_more_before_anything_was_told_still_works():
    prompt = build(question="再多說一點", more=True, last_told=None).prompt

    assert "還沒有播過" in prompt


def test_the_instructions_do_not_demonstrate_forbidden_phrasing():
    # 把規則寫進 LLM 的提示時，範本裡不能示範被禁止的寫法（tasks/lessons.md）
    assert "好問題" not in QA_INSTRUCTIONS


PHOTO = PhotoInput(path=Path("/home/x/.buddy-host/photos/abc.jpg"), compass_deg=270.0)


def test_a_photo_question_hands_over_the_file_and_lets_claude_read_it():
    request = build(photo=PHOTO, question="這是什麼？")

    assert "/home/x/.buddy-host/photos/abc.jpg" in request.prompt
    assert "Read" in request.prompt  # 明說要用 Read 工具看照片
    assert "Read" in request.allowed_tools
    assert set(WEB_TOOLS) <= set(request.allowed_tools)  # 上網的工具照舊
    assert request.add_dirs == (PHOTO.path.parent,)


def test_a_photo_question_uses_the_compass_not_the_travel_direction():
    request = build(photo=PHOTO, question="這是什麼？")

    assert "指南針" in request.prompt
    assert "西" in request.prompt  # 270 度
    assert "正朝" not in request.prompt  # 不是「走路的方向」


def test_a_photo_without_a_compass_reading_does_not_pretend_to_know_the_direction():
    request = build(photo=PhotoInput(PHOTO.path, None), question="這是什麼？")

    assert "指南針" not in request.prompt
    assert "拍照的方向不明" in request.prompt


def test_a_plain_question_cannot_read_files():
    request = build()

    assert "Read" not in request.allowed_tools
    assert request.add_dirs == ()


def test_the_instructions_tell_claude_not_to_describe_the_photo_like_a_report():
    # 問答是口說：要回答「這是什麼」，不是把照片逐項描述一遍
    assert "照片" in QA_INSTRUCTIONS
