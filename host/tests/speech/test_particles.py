import pytest

from buddy_host.speech.particles import CASES, SEEDS, classify, summarize
from buddy_host.speech.text_prep import numbers_to_chinese, remove_kana


def test_every_candidate_has_at_least_three_sentences_containing_the_word():
    for word, sentences in CASES.items():
        assert len(sentences) >= 3, word
        assert all(word in s for s in sentences), word


def test_there_are_at_least_three_seeds():
    assert len(SEEDS) >= 3


def test_ticket_candidates_are_all_covered():
    for word in ["哇", "對了", "而且", "其實", "你看", "欸", "啊", "喔", "吧", "啦"]:
        assert word in CASES


def test_sentences_need_no_preprocessing():
    for sentences in CASES.values():
        for s in sentences:
            assert numbers_to_chinese(remove_kana(s)) == s


@pytest.mark.parametrize(
    ("cers", "label"),
    [
        ([0.0] * 9, "safe"),
        ([0.0] * 8 + [0.5], "caution"),
        ([0.0] * 7 + [0.5, 0.9], "caution"),
        ([0.0] * 6 + [0.5, 0.9, 1.0], "unsafe"),
        ([1.0] * 9, "unsafe"),
    ],
)
def test_classify_by_pass_rate(cers, label):
    assert classify(cers, threshold=0.2) == label


def test_threshold_is_inclusive():
    assert classify([0.2] * 9, threshold=0.2) == "safe"


def test_summarize_groups_records_by_word():
    records = [
        {"word": "哇", "sentence_index": 0, "seed": 1, "cer": 0.0},
        {"word": "哇", "sentence_index": 0, "seed": 2, "cer": 0.5},
        {"word": "吧", "sentence_index": 0, "seed": 1, "cer": 0.0},
    ]

    summary = summarize(records, threshold=0.2)

    assert summary["哇"]["runs"] == 2
    assert summary["哇"]["passed"] == 1
    assert summary["哇"]["max_cer"] == 0.5
    assert summary["哇"]["mean_cer"] == pytest.approx(0.25)
    assert summary["吧"]["label"] == "safe"
