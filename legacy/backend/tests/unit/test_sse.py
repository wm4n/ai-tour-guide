"""Unit tests for SSE event encoding."""

from tour_guide.api.sse import encode_event


class TestEncodeEvent:
    """Tests for encode_event function."""

    def test_encode_text_event(self):
        """encode_event returns correct SSE format for text events."""
        result = encode_event("text", {"chunk": "hello"})
        assert result == 'event: text\ndata: {"chunk": "hello"}\n\n'

    def test_encode_meta_event(self):
        """encode_event returns correct SSE format for meta events."""
        result = encode_event("meta", {"cache_hit": False})
        expected = 'event: meta\ndata: {"cache_hit": false}\n\n'
        assert result == expected

    def test_sse_format_with_trailing_newlines(self):
        """SSE format always has exactly 2 trailing newlines."""
        result = encode_event("test", {"key": "value"})
        assert result.endswith("\n\n")
        assert not result.endswith("\n\n\n")
