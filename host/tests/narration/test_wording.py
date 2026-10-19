import json
from pathlib import Path

import pytest

from buddy_host.narration.wording import Finding, find_issues, load_terms

TERMS_FILE = Path(__file__).resolve().parents[2] / "config" / "taiwan_terms.json"


@pytest.fixture(scope="module")
def terms():
    return load_terms(TERMS_FILE)


def test_mainland_terms_are_flagged_with_the_taiwan_replacement(terms):
    issues = find_issues("這裡有一支介紹的視頻，還有軟件可以下載。", terms)

    assert Finding("視頻", "影片") in issues
    assert Finding("軟件", "軟體") in issues


@pytest.mark.parametrize(
    "text",
    [
        "搭捷運到大橋頭站，走路五分鐘就到迪化街。",
        "這間老茶行的品質很好，店家的資訊都在網路上。",
        "我們先搭公車再換計程車，到飯店放行李。",
    ],
)
def test_taiwan_wording_is_clean(terms, text):
    assert find_issues(text, terms) == []


def test_each_finding_is_reported_once_even_if_repeated(terms):
    issues = find_issues("視頻很好看，這個視頻是新的。", terms)

    assert issues.count(Finding("視頻", "影片")) == 1


def test_simplified_characters_leaking_into_the_script_are_flagged(terms):
    issues = find_issues("我们先走到这里，再看看那栋老房子。", terms)

    assert any(f.term == "簡體字" for f in issues)


def test_traditional_text_is_not_mistaken_for_simplified(terms):
    assert find_issues("我們先走到這裡，再看看那棟老房子。這座廟已經一百多年了。", terms) == []


def test_terms_file_is_well_formed_and_unambiguous():
    entries = json.loads(TERMS_FILE.read_text(encoding="utf-8"))

    assert len(entries) >= 25
    assert all(e["mainland"] and e["taiwan"] and e["mainland"] != e["taiwan"] for e in entries)
    assert len({e["mainland"] for e in entries}) == len(entries)
    # 替換詞本身不能又是要抓的詞，否則改完還是被抓
    mainland = {e["mainland"] for e in entries}
    assert not any(e["taiwan"] in mainland for e in entries)


def test_the_eight_fixed_phrases_contain_no_listed_mainland_term(terms):
    from buddy_host.speech.phrases import PHRASES

    for number, (text, _) in PHRASES.items():
        assert find_issues(text, terms) == [], number


def test_registered_as_a_historic_building_is_proper_taiwan_wording(terms):
    # 真實案例：Claude 寫「被登錄為歷史建築」，這是台灣文資的正規用語，不能當成大陸用語
    assert find_issues("後來被登錄為歷史建築，也登錄了文化資產。", terms) == []
