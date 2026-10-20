import pytest

from buddy_host.speech.text_prep import (
    chunk_sentences,
    numbers_to_chinese,
    prepare_paragraphs,
    prepare_sentences,
    remove_kana,
    split_sentences,
)


class TestYears:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2004年", "二零零四年"),
            ("2027年初", "二零二七年初"),
            ("在2026年10月", "在二零二六年十月"),
        ],
    )
    def test_four_digit_years_are_read_digit_by_digit(self, raw, expected):
        assert numbers_to_chinese(raw) == expected


class TestDates:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("10月17日", "十月十七日"),
            ("5月31日", "五月三十一日"),
            ("2月2日", "二月二日"),
            ("1月6日、7日休園", "一月六日、七日休園"),
            ("3號", "三號"),
            (
                "2026年10月17日一直到2027年5月31日",
                "二零二六年十月十七日一直到二零二七年五月三十一日",
            ),
        ],
    )
    def test_month_and_day_use_cardinals(self, raw, expected):
        assert numbers_to_chinese(raw) == expected


class TestQuantities:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("200公尺", "兩百公尺"),
            ("2個", "兩個"),
            ("20分鐘", "二十分鐘"),
            ("12個人", "十二個人"),
            ("105元", "一百零五元"),
            ("1005元", "一千零五元"),
            ("110公里", "一百一十公里"),
            ("3000人", "三千人"),
            ("2000人", "兩千人"),
            ("20000人", "兩萬人"),
            ("120000人", "十二萬人"),
            ("第3名", "第三名"),
            ("1,500人", "一千五百人"),
        ],
    )
    def test_integers_become_chinese_cardinals(self, raw, expected):
        assert numbers_to_chinese(raw) == expected

    def test_decimals(self):
        assert numbers_to_chinese("3.5公里") == "三點五公里"

    def test_percent(self):
        assert numbers_to_chinese("50%的人") == "百分之五十的人"

    def test_clock_time(self):
        assert numbers_to_chinese("10:30開門") == "十點三十分開門"
        assert numbers_to_chinese("9:00開門") == "九點開門"

    def test_range_becomes_dao(self):
        assert numbers_to_chinese("30～45秒") == "三十到四十五秒"

    def test_long_digit_strings_are_read_digit_by_digit(self):
        assert numbers_to_chinese("電話0223456789") == "電話零二二三四五六七八九"

    def test_text_without_digits_is_untouched(self):
        assert numbers_to_chinese("大稻埕是老街。") == "大稻埕是老街。"

    def test_is_idempotent(self):
        once = numbers_to_chinese("在2004年有200公尺")
        assert numbers_to_chinese(once) == once


class TestKana:
    def test_quoted_japanese_is_dropped_with_its_quotes(self):
        raw = "日文叫做「なばなの里」（Nabana no Sato）。"
        assert remove_kana(raw) == "日文叫做 Nabana no Sato。"

    def test_stray_kana_removed(self):
        assert remove_kana("這家店叫ラーメン屋") == "這家店叫屋"

    def test_prolonged_sound_mark_removed(self):
        assert "ー" not in remove_kana("ラーメン")

    def test_kanji_only_quotes_are_kept(self):
        assert remove_kana("叫做「大稻埕」。") == "叫做「大稻埕」。"

    def test_chinese_text_untouched(self):
        assert remove_kana("今天天氣很好。") == "今天天氣很好。"

    def test_latin_gets_spaces_next_to_chinese(self):
        assert remove_kana("大量LED燈光") == "大量 LED 燈光"


class TestSplit:
    def test_splits_on_terminal_punctuation_keeping_it(self):
        assert split_sentences("你好。今天好嗎？很好！") == ["你好。", "今天好嗎？", "很好！"]

    def test_newlines_also_split(self):
        assert split_sentences("第一行。\n第二行。") == ["第一行。", "第二行。"]

    def test_closing_quote_stays_with_its_sentence(self):
        assert split_sentences("他說「好。」然後走了。") == ["他說「好。」", "然後走了。"]

    def test_line_without_terminal_punctuation_gets_a_period(self):
        assert split_sentences("這裡有三個地方\n第一個是隧道。") == [
            "這裡有三個地方。",
            "第一個是隧道。",
        ]

    def test_blank_lines_and_whitespace_dropped(self):
        assert split_sentences("  \n甲。 \n\n乙。\n") == ["甲。", "乙。"]

    def test_empty_text(self):
        assert split_sentences("") == []

    def test_comma_ending_becomes_period(self):
        assert split_sentences("先走到這裡，") == ["先走到這裡。"]


def test_prepare_sentences_runs_the_whole_chain():
    raw = (
        "它位於三重縣，日文叫做「なばなの里」（Nabana no Sato）\n2004年開始辦燈飾，隧道長200公尺。"
    )

    assert prepare_sentences(raw) == [
        "它位於三重縣，日文叫做 Nabana no Sato。",
        "二零零四年開始辦燈飾，隧道長兩百公尺。",
    ]


class TestChunks:
    def test_short_sentences_merge_up_to_the_limit(self):
        sentences = ["甲" * 40 + "。", "乙" * 40 + "。", "丙" * 40 + "。"]

        assert chunk_sentences(sentences, limit=90) == [sentences[0] + sentences[1], sentences[2]]

    def test_interjection_is_merged_into_the_next_sentence(self):
        assert chunk_sentences(["哇！", "這是老街。"], limit=90) == ["哇！這是老街。"]

    def test_over_long_sentence_stays_alone(self):
        long = "甲" * 120 + "。"

        assert chunk_sentences(["乙。", long, "丙。"], limit=90) == ["乙。", long, "丙。"]

    def test_empty(self):
        assert chunk_sentences([], limit=90) == []


class TestSpecReviewEdgeCases:
    def test_four_digit_duration_is_a_quantity_not_a_year(self):
        assert numbers_to_chinese("1000年歷史") == "一千年歷史"
        assert numbers_to_chinese("兩千年以上") == "兩千年以上"
        assert numbers_to_chinese("2000年以上") == "兩千年以上"
        assert numbers_to_chinese("1800年的歷史") == "一千八百年的歷史"

    def test_year_followed_by_other_words_is_still_a_year(self):
        assert numbers_to_chinese("2004年開始") == "二零零四年開始"
        assert numbers_to_chinese("1895年以來") == "一八九五年以來"

    def test_year_range_reads_both_ends_as_years(self):
        assert numbers_to_chinese("1895～1945年") == "一八九五到一九四五年"

    def test_slash_date(self):
        assert numbers_to_chinese("10/18開放") == "十月十八日開放"
        assert numbers_to_chinese("1/6休園") == "一月六日休園"

    def test_slash_that_is_not_a_date_is_left_alone(self):
        assert numbers_to_chinese("50/60") == "五十/六十"


class TestParagraphs:
    def test_blank_lines_separate_paragraphs_and_each_is_prepared_on_its_own(self):
        raw = "我們到了。你看右邊。\n\n它有兩百年。\n\n\n\n最後一段"

        assert prepare_paragraphs(raw) == [
            ["我們到了。", "你看右邊。"],
            ["它有兩百年。"],
            ["最後一段。"],
        ]

    def test_single_line_breaks_stay_inside_the_paragraph(self):
        assert prepare_paragraphs("甲乙丙。\n丁戊己。") == [["甲乙丙。", "丁戊己。"]]

    def test_empty_text_has_no_paragraphs(self):
        assert prepare_paragraphs(" \n\n ") == []
