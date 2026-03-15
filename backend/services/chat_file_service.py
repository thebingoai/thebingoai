import base64
import csv
import io
import json
import logging
import uuid
from typing import Optional

import redis
from PIL import Image
import PyPDF2

from backend.config import settings
from backend.parser import csv_parser, docx_parser, pdf

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.redis_url, decode_responses=True)

CHAT_FILE_PREFIX = "chat_file:"

IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
SUPPORTED_IMAGE_FORMATS = {"PNG", "JPEG", "GIF", "WEBP"}

MIME_TO_CONTENT_TYPE = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "text/csv": "text",
    "application/pdf": "text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "text",
}


def _process_image(file_bytes: bytes, mime_type: str) -> dict:
    """Validate, optionally resize, and base64-encode an image."""
    image = Image.open(io.BytesIO(file_bytes))

    fmt = image.format or ""
    if fmt.upper() not in SUPPORTED_IMAGE_FORMATS:
        raise ValueError(f"Unsupported image format: {fmt}. Supported: PNG, JPEG, GIF, WEBP")

    # Resize if longest side > 2048px
    max_side = 2048
    width, height = image.size
    if max(width, height) > max_side:
        scale = max_side / max(width, height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.LANCZOS)
        logger.debug("Resized image from %dx%d to %dx%d", width, height, new_width, new_height)

    # Re-encode to bytes
    output = io.BytesIO()
    save_format = fmt.upper() if fmt.upper() in SUPPORTED_IMAGE_FORMATS else "PNG"
    # PIL uses "JPEG" not "JPG"
    image.save(output, format=save_format)
    encoded_bytes = output.getvalue()

    b64_data = base64.b64encode(encoded_bytes).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{b64_data}"

    return {
        "base64_data": data_uri,
        "metadata": {
            "width": image.size[0],
            "height": image.size[1],
            "format": save_format,
        },
    }


def _process_csv(file_bytes: bytes) -> dict:
    """Extract CSV text with truncation to max rows."""
    max_rows = settings.chat_file_csv_max_rows

    # Parse full file for metadata (row count, headers)
    full_result = csv_parser.extract_text(file_bytes)
    headers = full_result.get("headers", [])
    row_count = full_result.get("row_count", 0)

    # Build truncated version limited to max_rows
    content = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))

    lines = []
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append("-" * (sum(len(str(h)) for h in headers) + 3 * (len(headers) - 1)))

    truncated_rows = 0
    for i, row in enumerate(reader):
        if i >= max_rows:
            break
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))
        truncated_rows += 1

    truncated_text = "\n".join(lines).strip()

    return {
        "extracted_text": full_result["text"],
        "truncated_text": truncated_text,
        "metadata": {
            "headers": headers,
            "row_count": row_count,
            "truncated_rows": truncated_rows,
        },
    }


def _process_pdf(file_bytes: bytes) -> dict:
    """Extract PDF text; truncated version uses only first N pages."""
    max_pages = settings.chat_file_pdf_max_pages

    # Full extraction
    full_result = pdf.extract_text(file_bytes)
    full_text = full_result["text"]
    page_count = full_result["page_count"]

    # Truncated extraction: re-parse only first max_pages pages
    reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
    truncated_page_texts = []
    pages_to_read = min(max_pages, page_count)
    for page_num in range(pages_to_read):
        try:
            page_text = reader.pages[page_num].extract_text() or ""
            truncated_page_texts.append(page_text)
        except Exception as e:
            logger.warning("Failed to extract text from PDF page %d: %s", page_num, e)
            truncated_page_texts.append("")

    truncated_text = "\n\n".join(truncated_page_texts).strip()

    return {
        "extracted_text": full_text,
        "truncated_text": truncated_text,
        "metadata": {
            "page_count": page_count,
            "truncated_pages": pages_to_read,
        },
    }


def _process_docx(file_bytes: bytes) -> dict:
    """Extract DOCX text; truncated version is limited to max chars."""
    max_chars = settings.chat_file_text_max_chars

    result = docx_parser.extract_text(file_bytes)
    full_text = result["text"]
    paragraph_count = result.get("paragraph_count", 0)

    truncated_text = full_text[:max_chars]

    return {
        "extracted_text": full_text,
        "truncated_text": truncated_text,
        "metadata": {
            "paragraph_count": paragraph_count,
            "truncated_chars": len(truncated_text),
        },
    }


def process_file(file_bytes: bytes, filename: str, mime_type: str) -> dict:
    """
    Process a file using the appropriate parser.

    Returns a ChatFileData dict ready for storage.
    """
    content_type = MIME_TO_CONTENT_TYPE.get(mime_type)
    if content_type is None:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    file_id = str(uuid.uuid4())
    size = len(file_bytes)

    file_data: dict = {
        "file_id": file_id,
        "original_name": filename,
        "mime_type": mime_type,
        "size": size,
        "content_type": content_type,
    }

    if content_type == "image":
        image_result = _process_image(file_bytes, mime_type)
        file_data["base64_data"] = image_result["base64_data"]
        file_data["metadata"] = image_result["metadata"]
    else:
        # Text-based content
        if mime_type == "text/csv":
            text_result = _process_csv(file_bytes)
        elif mime_type == "application/pdf":
            text_result = _process_pdf(file_bytes)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text_result = _process_docx(file_bytes)
        else:
            raise ValueError(f"No parser available for MIME type: {mime_type}")

        file_data["extracted_text"] = text_result["extracted_text"]
        file_data["truncated_text"] = text_result["truncated_text"]
        file_data["metadata"] = text_result["metadata"]

    return file_data


def store_file(file_data: dict) -> str:
    """
    Store ChatFileData in Redis with 1-hour TTL.

    Returns the file_id (UUID string).
    """
    file_id = file_data["file_id"]
    key = f"{CHAT_FILE_PREFIX}{file_id}"
    redis_client.setex(key, settings.chat_file_ttl_seconds, json.dumps(file_data))
    logger.debug("Stored chat file %s (expires in %ds)", file_id, settings.chat_file_ttl_seconds)
    return file_id


def get_file(file_id: str) -> Optional[dict]:
    """Retrieve ChatFileData from Redis. Returns None if not found or expired."""
    key = f"{CHAT_FILE_PREFIX}{file_id}"
    data = redis_client.get(key)
    if data is None:
        return None
    return json.loads(data)


def get_truncated_content(file_id: str) -> str:
    """
    Return the truncated text for chat context.

    For image files, returns an empty string (use base64_data directly).
    Raises KeyError if file_id is not found.
    """
    file_data = get_file(file_id)
    if file_data is None:
        raise KeyError(f"Chat file not found: {file_id}")
    return file_data.get("truncated_text", "")


def get_full_content(file_id: str) -> str:
    """
    Return the full extracted text.

    For image files, returns an empty string (use base64_data directly).
    Raises KeyError if file_id is not found.
    """
    file_data = get_file(file_id)
    if file_data is None:
        raise KeyError(f"Chat file not found: {file_id}")
    return file_data.get("extracted_text", "")
