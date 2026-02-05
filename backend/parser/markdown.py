import tiktoken
import re
from typing import Optional

# Initialize tokenizer
_tokenizer: Optional[tiktoken.Encoding] = None

def get_tokenizer() -> tiktoken.Encoding:
    """Get or create tokenizer instance."""
    global _tokenizer
    if _tokenizer is None:
        _tokenizer = tiktoken.encoding_for_model("gpt-4")
    return _tokenizer

def count_tokens(text: str) -> int:
    """Count tokens in text."""
    tokenizer = get_tokenizer()
    return len(tokenizer.encode(text))

def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Simple sentence splitter - handles common cases
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

def chunk_markdown(
    text: str,
    chunk_size: int = 512,
    overlap: float = 0.2
) -> list[dict]:
    """
    Split markdown into overlapping chunks.

    Args:
        text: Raw markdown text
        chunk_size: Target tokens per chunk
        overlap: Overlap ratio (0.0 to 0.5)

    Returns:
        List of chunk dicts with index, text, token_count, char_start, char_end
    """
    if not text.strip():
        return []

    tokenizer = get_tokenizer()
    overlap_tokens = int(chunk_size * overlap)

    # Split by double newlines (paragraphs) first
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk_texts = []
    current_chunk_tokens = 0
    char_position = 0

    def finalize_chunk():
        """Create a chunk from accumulated texts."""
        nonlocal current_chunk_texts, current_chunk_tokens, char_position

        if not current_chunk_texts:
            return

        chunk_text = "\n\n".join(current_chunk_texts)
        chunk_start = text.find(current_chunk_texts[0], char_position)
        if chunk_start == -1:
            chunk_start = char_position
        chunk_end = chunk_start + len(chunk_text)

        chunks.append({
            "index": len(chunks),
            "text": chunk_text,
            "token_count": current_chunk_tokens,
            "char_start": chunk_start,
            "char_end": chunk_end
        })

        # Calculate overlap - keep last N tokens worth of text
        if overlap_tokens > 0 and current_chunk_texts:
            overlap_texts = []
            overlap_count = 0
            for t in reversed(current_chunk_texts):
                t_tokens = count_tokens(t)
                if overlap_count + t_tokens <= overlap_tokens:
                    overlap_texts.insert(0, t)
                    overlap_count += t_tokens
                else:
                    break
            current_chunk_texts = overlap_texts
            current_chunk_tokens = overlap_count
        else:
            current_chunk_texts = []
            current_chunk_tokens = 0

        char_position = chunk_end

    for para in paragraphs:
        para_tokens = count_tokens(para)

        # If single paragraph exceeds chunk_size, split by sentences
        if para_tokens > chunk_size:
            # Finalize current chunk first
            if current_chunk_texts:
                finalize_chunk()

            sentences = split_into_sentences(para)
            for sent in sentences:
                sent_tokens = count_tokens(sent)

                # If single sentence exceeds chunk_size, force split by tokens
                if sent_tokens > chunk_size:
                    tokens = tokenizer.encode(sent)
                    for i in range(0, len(tokens), chunk_size - overlap_tokens):
                        chunk_tokens = tokens[i:i + chunk_size]
                        chunk_text = tokenizer.decode(chunk_tokens)
                        chunk_start = text.find(chunk_text[:50], char_position)
                        if chunk_start == -1:
                            chunk_start = char_position

                        chunks.append({
                            "index": len(chunks),
                            "text": chunk_text,
                            "token_count": len(chunk_tokens),
                            "char_start": chunk_start,
                            "char_end": chunk_start + len(chunk_text)
                        })
                        char_position = chunk_start + len(chunk_text)
                else:
                    if current_chunk_tokens + sent_tokens > chunk_size:
                        finalize_chunk()
                    current_chunk_texts.append(sent)
                    current_chunk_tokens += sent_tokens
        else:
            # Normal paragraph - check if it fits
            if current_chunk_tokens + para_tokens > chunk_size:
                finalize_chunk()
            current_chunk_texts.append(para)
            current_chunk_tokens += para_tokens

    # Don't forget the last chunk
    if current_chunk_texts:
        finalize_chunk()

    return chunks


def extract_metadata(text: str) -> dict:
    """Extract YAML frontmatter if present."""
    metadata = {}

    # Check for YAML frontmatter
    if text.startswith("---"):
        end_match = re.search(r'\n---\s*\n', text[3:])
        if end_match:
            yaml_content = text[3:end_match.start() + 3]
            try:
                import yaml
                metadata = yaml.safe_load(yaml_content) or {}
            except Exception:
                pass

    return metadata
