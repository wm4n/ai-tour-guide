from pathlib import Path

PERSONA = Path(__file__).resolve().parents[2] / "config" / "buddy.md"

# 實測結論見 docs/spikes/2026-10-19-particles/；改結論時兩邊要一起改
AVOID = ["欸", "啊", "喔", "吧", "一下下", "哇", "呢"]
ALLOWED = ["對了", "而且", "其實", "你看", "啦"]


def rule_lines() -> dict[str, str]:
    lines = PERSONA.read_text(encoding="utf-8").splitlines()
    return {
        "avoid": next(line for line in lines if "**不要用**" in line),
        "allowed": next(line for line in lines if "**可以用**" in line),
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


def test_the_example_script_does_not_use_any_word_the_rules_forbid():
    # few-shot 範例比規則更有說服力：範本若示範「哇！」，Claude 就會照做
    text = PERSONA.read_text(encoding="utf-8")
    example = text[text.index("## 範本") :]

    assert [word for word in AVOID if word in example] == []


def test_persona_tells_claude_to_use_taiwan_wording_with_examples():
    text = PERSONA.read_text(encoding="utf-8")

    for taiwan in ("影片", "軟體", "捷運", "公車", "計程車", "飯店"):
        assert taiwan in text


def test_the_example_script_uses_no_listed_mainland_term():
    from buddy_host.narration.wording import find_issues, load_terms

    terms_file = Path(__file__).resolve().parents[2] / "config" / "taiwan_terms.json"
    text = PERSONA.read_text(encoding="utf-8")
    example = text[text.index("## 範本") :]

    assert find_issues(example, load_terms(terms_file)) == []


def test_persona_keeps_the_opening_sentence_off_a_proper_noun():
    # 句首是冷啟動，開場又是人名、廟名這類罕用字時，合成最容易失敗而整句被跳過（#6 實測）
    text = PERSONA.read_text(encoding="utf-8")

    assert "第一句" in text
    assert "專有名詞" in text


def test_persona_asks_for_short_paragraphs_so_the_voice_can_breathe():
    # 空行在朗讀時會停得比句間久（#6 試聽回饋：一股腦唸像在念稿）
    text = PERSONA.read_text(encoding="utf-8")

    assert "空一行" in text
    assert "看一下" in text


def test_persona_talks_like_a_friend_not_an_encyclopedia():
    # 試聽回饋：像在念稿。要的是暖場、傳聞八卦、轉述來源，而且只用資料裡真有的（不編造）
    text = PERSONA.read_text(encoding="utf-8")

    for phrase in ("暖場", "傳聞", "八卦", "我讀過", "不要編"):
        assert phrase in text


def test_persona_never_makes_him_apologise_for_old_data():
    text = PERSONA.read_text(encoding="utf-8")

    assert "道歉" in text  # 規則本身要點名，Claude 才知道不能這樣寫
    assert "資料可能過時" not in text.split("## 範本")[1]


def test_persona_explains_how_to_use_the_traveler_state():
    text = PERSONA.read_text(encoding="utf-8")

    assert "他現在的狀態" in text
