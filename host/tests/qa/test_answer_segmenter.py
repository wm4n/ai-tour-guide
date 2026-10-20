from buddy_host.qa.segmenter import AnswerSegmenter


def run(text: str, chunk: int | None = None, **kw) -> list[str]:
    """把文字餵進分段器（可以一次餵完，也可以每 chunk 個字餵一次），回傳依序吐出的段落。"""
    segmenter = AnswerSegmenter(**kw)
    out: list[str] = []
    pieces = [text] if chunk is None else [text[i : i + chunk] for i in range(0, len(text), chunk)]
    for piece in pieces:
        out += segmenter.feed(piece)
    return out + segmenter.finish()


def test_the_first_segment_is_the_first_sentence_as_soon_as_it_is_complete():
    segmenter = AnswerSegmenter()

    assert segmenter.feed("那間廟拜的是城隍爺") == []  # 句子還沒寫完
    assert segmenter.feed("，保佑生意興隆。後面的還在寫") == ["那間廟拜的是城隍爺，保佑生意興隆。"]


def test_a_very_short_first_sentence_is_merged_with_the_next_one():
    # 太短的句子單獨合成很容易驗收失敗（見語音管線）
    assert (
        run("對！是城隍爺，大家都這樣說。後面還有。", min_first_chars=10)[0]
        == "對！是城隍爺，大家都這樣說。"
    )


def test_later_sentences_are_grouped_up_to_the_size_limit():
    sentence = "這是一句大約十五個字的話喔。"  # 14 字
    text = sentence * 6

    segments = run(text, min_first_chars=5, later_max_chars=30)

    assert segments[0] == sentence
    assert all(len(s) <= 30 for s in segments[1:])
    assert "".join(segments) == text  # 不遺漏、不重複


def test_streaming_in_tiny_pieces_gives_the_same_segments_as_feeding_it_all_at_once():
    text = "好的。城隍爺是這裡的主神，香火很旺。我聽說他很靈！你可以順便走走看看周圍。"

    assert run(text, chunk=1) == run(text)


def test_finish_flushes_what_is_left_even_without_a_sentence_ending():
    segmenter = AnswerSegmenter()
    assert segmenter.feed("第一句還太短。") == []  # 不到最短長度，先留著
    assert segmenter.finish() == ["第一句還太短。"]

    segmenter = AnswerSegmenter()
    assert segmenter.feed("沒有句號的答案") == []
    assert segmenter.finish() == ["沒有句號的答案"]


def test_a_newline_ends_a_sentence():
    assert run("沒有標點的第一行\n第二行也是", min_first_chars=5) == [
        "沒有標點的第一行",
        "第二行也是",
    ]


def test_closing_quotes_stay_with_their_sentence():
    assert run("他說「好啊。」然後走了。", min_first_chars=3)[0] == "他說「好啊。」"


def test_discard_drops_what_was_not_yet_emitted_such_as_a_lead_in_before_a_web_search():
    segmenter = AnswerSegmenter(min_first_chars=20)
    assert segmenter.feed("我來查一下。") == []  # 還太短，沒有吐出
    segmenter.discard()
    segmenter.feed("查到了，營業到晚上九點。")

    assert segmenter.finish() == ["查到了，營業到晚上九點。"]


def test_empty_input_produces_nothing():
    assert run("") == []
    assert run("  \n ") == []
