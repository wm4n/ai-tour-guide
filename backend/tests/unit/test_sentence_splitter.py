"""Tests for SentenceSplitter module (TDD: write first, then implement)."""

from tour_guide.pipeline.sentence_splitter import StreamingSentenceBuffer, split_complete_text

# ---------------------------------------------------------------------------
# split_complete_text tests
# ---------------------------------------------------------------------------


class TestSplitCompleteText:
    def test_chinese_punctuation(self):
        result = split_complete_text("故宮博物院位於台北市。始建於1925年。")
        assert result == ["故宮博物院位於台北市。", "始建於1925年。"]

    def test_english_period_and_question(self):
        result = split_complete_text("Hello world. How are you?")
        assert result == ["Hello world.", " How are you?"]

    def test_mixed_chinese_english_punctuation(self):
        result = split_complete_text("台北很美。It is great! 歡迎來訪。")
        assert result == ["台北很美。", "It is great!", " 歡迎來訪。"]

    def test_empty_string(self):
        result = split_complete_text("")
        assert result == []

    def test_no_punctuation(self):
        result = split_complete_text("hello")
        assert result == ["hello"]

    def test_exclamation_mark(self):
        result = split_complete_text("太棒了！真的很好！")  # noqa: RUF001
        assert result == ["太棒了！", "真的很好！"]  # noqa: RUF001

    def test_question_mark_chinese(self):
        result = split_complete_text("你好嗎？我很好。")  # noqa: RUF001
        assert result == ["你好嗎？", "我很好。"]  # noqa: RUF001

    def test_single_sentence(self):
        result = split_complete_text("只有一句話。")
        assert result == ["只有一句話。"]


# ---------------------------------------------------------------------------
# StreamingSentenceBuffer tests
# ---------------------------------------------------------------------------


class TestStreamingSentenceBuffer:
    def test_feed_yields_complete_sentence_after_punctuation(self):
        buf = StreamingSentenceBuffer()
        result1 = buf.feed("故宮博物院")
        assert result1 == []  # no punctuation yet

        result2 = buf.feed("位於台北市。")
        assert result2 == ["故宮博物院位於台北市。"]

    def test_feed_english_multiple_chunks(self):
        buf = StreamingSentenceBuffer()
        buf.feed("Hello")
        result = buf.feed(" world.")
        assert result == ["Hello world."]

    def test_feed_partial_then_flush(self):
        buf = StreamingSentenceBuffer()
        buf.feed("Hello")
        buf.feed(" world.")
        buf.feed(" Bye?")  # ends with ?, so sentence is complete
        remainder = buf.flush()
        assert remainder is None or remainder == ""

    def test_flush_returns_remaining_incomplete_sentence(self):
        buf = StreamingSentenceBuffer()
        buf.feed("Hello")
        buf.feed(" world.")
        buf.feed(" incomplete")
        remainder = buf.flush()
        assert remainder == " incomplete"

    def test_feed_yields_multiple_sentences_in_one_chunk(self):
        buf = StreamingSentenceBuffer()
        result = buf.feed("Hello. Bye?")
        assert result == ["Hello.", " Bye?"]

    def test_flush_empty_buffer(self):
        buf = StreamingSentenceBuffer()
        result = buf.flush()
        assert result is None or result == ""

    def test_feed_then_flush_sequence(self):
        buf = StreamingSentenceBuffer()
        buf.feed("Hello")
        r1 = buf.feed(" world.")
        assert r1 == ["Hello world."]

        buf.feed(" Bye?")
        r2 = buf.flush()
        # " Bye?" ends with ?, buffer should be empty
        assert r2 is None or r2 == ""

    def test_feed_mixed_punctuation_streaming(self):
        buf = StreamingSentenceBuffer()
        r1 = buf.feed("台北很美")
        assert r1 == []
        r2 = buf.feed("。It is")
        assert r2 == ["台北很美。"]
        r3 = buf.feed(" great!")
        assert r3 == ["It is great!"]
        remainder = buf.flush()
        assert remainder is None or remainder == ""
