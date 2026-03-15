import io
import logging

import docx

logger = logging.getLogger(__name__)


def extract_text(file_bytes: bytes) -> dict:
    """
    Extract text from a DOCX file.

    Args:
        file_bytes: Raw bytes of the DOCX file

    Returns:
        dict with keys:
            - text: Extracted paragraph text joined with newlines
            - paragraph_count: Number of paragraphs in the document
    """
    document = docx.Document(io.BytesIO(file_bytes))

    paragraphs = [para.text for para in document.paragraphs]
    paragraph_count = len(paragraphs)

    # Filter empty paragraphs for the text output but preserve count
    non_empty = [p for p in paragraphs if p.strip()]
    text = "\n".join(non_empty).strip()

    return {
        "text": text,
        "paragraph_count": paragraph_count,
    }
