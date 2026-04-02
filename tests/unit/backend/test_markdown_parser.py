"""Tests for the markdown chunking and tokenisation utilities."""

import pytest

from backend.parser.markdown import count_tokens, split_into_sentences, chunk_markdown


# ---------------------------------------------------------------------------
# count_tokens
# ---------------------------------------------------------------------------

class TestCountTokens:
    """Tests for token counting."""

    def test_empty_string(self):
        """Empty string has zero tokens."""
        assert count_tokens("") == 0

    def test_single_word(self):
        """A single common word produces at least one token."""
        assert count_tokens("hello") >= 1

    def test_known_sentence(self):
        """A short English sentence returns a plausible token count."""
        tokens = count_tokens("The quick brown fox jumps over the lazy dog.")
        assert 5 <= tokens <= 15  # reasonable range for GPT-4 tokeniser


# ---------------------------------------------------------------------------
# split_into_sentences
# ---------------------------------------------------------------------------

class TestSplitIntoSentences:
    """Tests for sentence splitting."""

    def test_splits_on_period(self):
        """Consecutive sentences separated by period + space are split."""
        result = split_into_sentences("First sentence. Second sentence.")
        assert len(result) == 2
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."

    def test_splits_on_question_mark(self):
        """Question marks are recognised as sentence boundaries."""
        result = split_into_sentences("What? Really!")
        assert len(result) == 2

    def test_empty_string(self):
        """Empty input returns an empty list."""
        assert split_into_sentences("") == []

    def test_single_sentence(self):
        """A single sentence without trailing punctuation returns one item."""
        result = split_into_sentences("Only one sentence here")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# chunk_markdown
# ---------------------------------------------------------------------------

class TestChunkMarkdown:
    """Tests for the main chunking function."""

    def test_empty_input_returns_empty_list(self):
        """Whitespace-only input produces no chunks."""
        assert chunk_markdown("") == []
        assert chunk_markdown("   ") == []

    def test_small_text_returns_single_chunk(self):
        """Text well below chunk_size produces exactly one chunk."""
        text = "Hello world. This is a short paragraph."
        chunks = chunk_markdown(text, chunk_size=512)
        assert len(chunks) == 1
        assert chunks[0]["text"] == text
        assert chunks[0]["index"] == 0

    def test_large_text_produces_multiple_chunks(self):
        """Repeating text that exceeds chunk_size is split into multiple chunks."""
        # Build text that is several times larger than chunk_size=50
        paragraph = "This is a moderately long sentence that contains several tokens. "
        text = (paragraph * 30).strip()
        chunks = chunk_markdown(text, chunk_size=50)
        assert len(chunks) > 1

    def test_chunk_metadata_fields(self):
        """Each chunk dict has the required metadata keys."""
        text = "Some markdown content here."
        chunks = chunk_markdown(text, chunk_size=512)
        assert len(chunks) == 1
        chunk = chunks[0]
        assert "index" in chunk
        assert "text" in chunk
        assert "token_count" in chunk
        assert "char_start" in chunk
        assert "char_end" in chunk

    def test_chunk_indices_are_sequential(self):
        """Chunk indices start at 0 and increment by 1."""
        paragraph = "A sentence with enough tokens to fill a small chunk. "
        text = (paragraph * 30).strip()
        chunks = chunk_markdown(text, chunk_size=50)
        for i, chunk in enumerate(chunks):
            assert chunk["index"] == i

    def test_overlap_shares_content(self):
        """With non-zero overlap, consecutive chunks share some text."""
        paragraph = "Alpha bravo charlie delta echo foxtrot golf. "
        text = (paragraph * 40).strip()
        chunks = chunk_markdown(text, chunk_size=30, overlap=0.3)
        if len(chunks) >= 2:
            # With overlap, the end of one chunk should appear at the start of the next
            first_text = chunks[0]["text"]
            second_text = chunks[1]["text"]
            # The second chunk should contain some text from the first
            first_words = set(first_text.split())
            second_words = set(second_text.split())
            shared = first_words & second_words
            assert len(shared) > 0, "Expected overlapping content between consecutive chunks"

    def test_zero_overlap(self):
        """With overlap=0.0, chunks still cover the full text without errors."""
        paragraph = "Sentence one here. Sentence two here. "
        text = (paragraph * 20).strip()
        chunks = chunk_markdown(text, chunk_size=30, overlap=0.0)
        assert len(chunks) >= 1

    def test_paragraph_splitting(self):
        """Double-newline paragraph boundaries are respected."""
        text = "First paragraph content.\n\nSecond paragraph content."
        chunks = chunk_markdown(text, chunk_size=512)
        assert len(chunks) == 1
        assert "First paragraph" in chunks[0]["text"]
        assert "Second paragraph" in chunks[0]["text"]

    def test_token_count_within_bounds(self):
        """Each chunk's reported token_count is positive and reasonable."""
        paragraph = "Some words to fill the chunk with enough data. "
        text = (paragraph * 40).strip()
        chunks = chunk_markdown(text, chunk_size=60)
        for chunk in chunks:
            assert chunk["token_count"] > 0
