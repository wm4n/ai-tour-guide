import pytest

from buddy_host.speech.cer import cer, normalize


def test_identical_text_has_zero_cer():
    assert cer("今天天氣很好。", "今天天氣很好") == 0.0


def test_punctuation_spaces_and_case_are_ignored():
    assert cer("日文叫做 Nabana no Sato。", "日文叫做nabana no sato") == 0.0


def test_simplified_whisper_output_matches_traditional_script():
    assert cer("這裡有一條隧道", "这里有一条隧道") == 0.0


def test_one_substitution_out_of_four():
    assert cer("大稻埕街", "大稻埕路") == pytest.approx(0.25)


def test_empty_hypothesis_is_total_failure():
    assert cer("大稻埕", "") == 1.0


def test_empty_reference_is_zero():
    assert cer("", "隨便") == 0.0


@pytest.mark.parametrize(
    ("reference", "hypothesis"),
    [
        ("二零二七年初", "2027年初"),
        ("二零二六年十月十七日", "2026年10月17日"),
        ("長達兩百公尺", "長達200公尺"),
        ("長達兩百公尺", "長達二百公尺"),
        ("只有一月六日、七日休園", "只有1月6日、7日休園"),
        ("百分之五十", "50%"),
    ],
)
def test_arabic_and_chinese_numerals_are_unified(reference, hypothesis):
    assert cer(reference, hypothesis) == 0.0


def test_genuinely_wrong_number_still_counts():
    assert cer("二零二七年", "二零二八年") > 0


def test_normalize_is_stable():
    assert normalize("2027年") == normalize(normalize("2027年"))


@pytest.mark.parametrize(
    ("reference", "hypothesis"),
    [
        ("台北霞海城隍廟", "台北霞海城黃廟"),  # 「隍」罕用，Whisper 寫成同音的「黃」
        ("它在迪化街上", "他在迪化街上"),
        ("她在迪化街上", "他在迪化街上"),
    ],
)
def test_homophone_spellings_whisper_prefers_are_unified(reference, hypothesis):
    assert cer(reference, hypothesis) == 0.0


def test_homophone_unification_does_not_hide_other_errors():
    assert cer("台北霞海城隍廟", "台北霞海城黃苗") > 0
