from pathlib import Path

PERSONA = Path(__file__).resolve().parents[2] / "config" / "buddy.md"

# 實測結論見 docs/spikes/2026-10-19-particles/；改結論時兩邊要一起改
AVOID = ["欸", "啊", "喔", "吧", "一下下", "哇", "呢"]
ALLOWED = ["對了", "而且", "其實", "你看", "啦"]


def rule_lines() -> dict[str, str]:
    lines = PERSONA.read_text(encoding="utf-8").splitlines()
    return {
        "avoid": next(line for line in lines if "不要用" in line),
        "allowed": next(line for line in lines if "可以用" in line),
    }


def test_avoid_list_names_every_unsafe_particle():
    avoid = rule_lines()["avoid"]

    assert all(word in avoid for word in AVOID)
    assert not any(word in avoid for word in ALLOWED)


def test_allowed_list_names_the_safe_particles():
    allowed = rule_lines()["allowed"]

    assert all(word in allowed for word in ALLOWED)


def test_persona_keeps_the_number_and_kana_rules():
    text = PERSONA.read_text(encoding="utf-8")

    assert "二零二七年" in text
    assert "假名" in text
