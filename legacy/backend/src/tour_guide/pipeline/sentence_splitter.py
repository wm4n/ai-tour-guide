"""Sentence splitting utilities for tour guide narration pipeline."""

import re

# Punctuation marks that terminate a sentence (Chinese and English).

_TERMINATORS_PATTERN = r"[。！？.!?]"  # noqa: RUF001


def split_complete_text(text: str) -> list[str]:
    """Split a complete text into sentences at Chinese and English punctuation.

    Punctuation is included at the end of each sentence. Any trailing text
    without a terminator is returned as the last item.

    Args:
        text: The full text to split.

    Returns:
        A list of sentences. Empty input returns [].
    """
    if not text:
        return []

    parts = re.split(r"(?<=[。！？.!?])", text)  # noqa: RUF001

    # Filter empty strings that can arise from trailing punctuation
    return [p for p in parts if p]


class StreamingSentenceBuffer:
    """Accumulates streaming text chunks and yields complete sentences.

    Usage::

        buf = StreamingSentenceBuffer()
        for chunk in stream:
            for sentence in buf.feed(chunk):
                process(sentence)
        remainder = buf.flush()
        if remainder:
            process(remainder)
    """

    def __init__(self) -> None:
        self._buffer: str = ""

    def feed(self, chunk: str) -> list[str]:
        """Append *chunk* to the internal buffer and return any complete sentences.

        A sentence is considered complete when it ends with a terminating
        punctuation mark (Chinese or English).

        Args:
            chunk: The next piece of text from the stream.

        Returns:
            A (possibly empty) list of complete sentences found after appending
            the chunk.
        """
        self._buffer += chunk
        sentences = split_complete_text(self._buffer)

        if not sentences:
            return []

        # Check whether the last part ends with a terminator
        last = sentences[-1]
        if re.search(r"[。！？.!?]$", last):  # noqa: RUF001
            # All parts are complete sentences
            self._buffer = ""
            return sentences
        else:
            # Last part has no terminator — keep it in the buffer
            self._buffer = last
            return sentences[:-1]

    def flush(self) -> str | None:
        """Return and clear any remaining buffered text.

        Returns:
            The remaining buffer content, or ``None`` if the buffer is empty.
        """
        remaining = self._buffer
        self._buffer = ""
        return remaining if remaining else None
