from buddy_host.speech.phrases import CANDIDATE_SEEDS, PHRASES, WANTED
from buddy_host.speech.text_prep import prepare_sentences


def test_there_are_eight_numbered_phrases_matching_the_design_doc():
    assert sorted(PHRASES) == [1, 2, 3, 4, 5, 6, 7, 8]
    assert PHRASES[7][0] == "好，我們出發吧！"


def test_phrases_need_no_preprocessing_beyond_a_terminal_mark():
    for text, _ in PHRASES.values():
        assert (
            "".join(prepare_sentences(text)) == text
            or "".join(prepare_sentences(text)) == text + "。"
        )


def test_enough_seeds_to_find_the_wanted_candidates():
    assert len(CANDIDATE_SEEDS) >= WANTED * 2
