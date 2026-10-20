import pytest

from buddy_host.speech.preroll import WordTiming, analyze_preroll


def w(word: str, start: float, end: float | None = None) -> WordTiming:
    return WordTiming(word, start, start + 0.2 if end is None else end)


def test_clean_start_needs_no_trim():
    verdict = analyze_preroll("我恢復了，我們繼續。", [w("我", 0.0), w("恢", 0.26), w("復", 0.54)])

    assert verdict.ok and verdict.trim_to is None and verdict.reason is None


def test_small_lead_in_is_tolerated():
    verdict = analyze_preroll("好，我們出發吧！", [w("好,", 0.25), w("我們", 0.7)])

    assert verdict.ok and verdict.trim_to is None


def test_long_lead_in_is_trimmed_to_just_before_the_first_word():
    verdict = analyze_preroll("我上網查一下", [w("我", 0.96), w("上", 1.24), w("網", 1.38)])

    assert verdict.ok
    assert verdict.trim_to == pytest.approx(0.96 - 0.15)
    assert "lead-in" in verdict.reason


def test_leading_filler_is_cut_and_the_real_start_is_found():
    words = [w("呃", 0.0), w("我", 0.8), w("恢", 1.0), w("復", 1.2)]

    verdict = analyze_preroll("我恢復了", words)

    assert verdict.ok
    assert verdict.trim_to == pytest.approx(0.8 - 0.15)
    assert "filler" in verdict.reason


def test_filler_with_no_recognisable_real_start_is_rejected():
    verdict = analyze_preroll("我恢復了", [w("呃", 0.0)])

    assert not verdict.ok
    assert "filler" in verdict.reason


def test_text_that_really_starts_with_the_filler_is_fine():
    verdict = analyze_preroll("啊，原來這就是老店。", [w("啊", 0.0), w("原", 0.4), w("來", 0.5)])

    assert verdict.ok and verdict.trim_to is None


def test_wrong_first_word_is_rejected_even_if_the_rest_is_fine():
    # 真實案例：「額度用完了」被念成「眾珠用完了」，CER 0.167 仍會過關
    verdict = analyze_preroll("額度用完了", [w("眾", 0.0), w("珠", 0.4), w("用", 0.6)])

    assert not verdict.ok
    assert "first word" in verdict.reason


def test_no_words_at_all_is_rejected():
    assert not analyze_preroll("我恢復了", []).ok


def test_punctuation_only_tokens_are_ignored():
    verdict = analyze_preroll("好，我們出發吧！", [w(",", 0.0), w("好", 0.1), w("我們", 0.5)])

    assert verdict.ok and verdict.trim_to is None


def test_arabic_numerals_still_match_a_chinese_numeral_start():
    verdict = analyze_preroll("二零零四年開始", [w("2004年", 0.0), w("開始", 0.8)])

    assert verdict.ok
