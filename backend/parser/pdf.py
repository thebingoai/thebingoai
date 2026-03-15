import io
import logging
from typing import Optional

import PyPDF2

logger = logging.getLogger(__name__)


def extract_text(file_bytes: bytes) -> dict:
    """
    Extract text from a PDF file.

    Args:
        file_bytes: Raw bytes of the PDF file

    Returns:
        dict with keys:
            - text: Extracted text content joined across all pages
            - page_count: Number of pages in the PDF
    """
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    page_count = len(reader.pages)

    page_texts = []
    for page_num, page in enumerate(reader.pages):
        try:
            page_text = page.extract_text() or ""
            page_texts.append(page_text)
        except Exception as e:
            logger.warning("Failed to extract text from page %d: %s", page_num, e)
            page_texts.append("")

    text = "\n\n".join(page_texts).strip()

    return {
        "text": text,
        "page_count": page_count,
    }
