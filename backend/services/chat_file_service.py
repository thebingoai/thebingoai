import base64
import csv
import io
import json
import logging
import os
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

EXCEL_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DATASET_MIME_TYPES = {"text/csv", EXCEL_MIME_TYPE}

MIME_TO_CONTENT_TYPE = {
    "image/png": "image",
    "image/jpeg": "image",
    "image/gif": "image",
    "image/webp": "image",
    "text/csv": "text",
    "application/pdf": "text",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "text",
    EXCEL_MIME_TYPE: "text",
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
    """Extract CSV text with statistical profiling."""
    import pandas as pd
    from backend.profiler.dataset_profiler import profile_dataframe

    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
    except Exception:
        # Fallback: try latin-1 encoding
        df = pd.read_csv(io.BytesIO(file_bytes), encoding="latin-1")

    headers = list(df.columns)
    row_count = len(df)

    # Generate statistical profile
    try:
        profile = profile_dataframe(df)
        profile_text = profile.to_prompt_text("")  # filename injected at message build time
        profiled = True
    except Exception as exc:
        logger.warning("Dataset profiling failed, using truncated text: %s", exc)
        profile_text = None
        profiled = False

    # Build sample text for truncated_text (backward compat + small sample)
    sample_rows = min(settings.profile_sample_rows, row_count)
    lines = []
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append("-" * (sum(len(str(h)) for h in headers) + 3 * (len(headers) - 1)))
    for _, row in df.head(sample_rows).iterrows():
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))
    truncated_text = "\n".join(lines).strip()

    result = {
        "extracted_text": truncated_text,
        "truncated_text": truncated_text,
        "metadata": {
            "headers": headers,
            "row_count": row_count,
            "truncated_rows": sample_rows,
            "profiled": profiled,
        },
    }
    if profile_text:
        result["profile_text"] = profile_text
    return result


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


def _process_excel(file_bytes: bytes) -> dict:
    """Extract Excel text preview with statistical profiling."""
    try:
        import pandas as pd
    except ImportError:
        # pandas not available — fall back to openpyxl with no profiling
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
            if not rows:
                return {"extracted_text": "", "truncated_text": "", "metadata": {"headers": [], "row_count": 0, "truncated_rows": 0, "profiled": False}}
            headers = [str(h) if h is not None else "" for h in rows[0]]
            max_rows = settings.chat_file_csv_max_rows
            data_rows = rows[1:]
            lines = [" | ".join(headers)]
            lines.append("-" * (sum(len(h) for h in headers) + 3 * (len(headers) - 1)))
            truncated_rows = min(len(data_rows), max_rows)
            for row in data_rows[:max_rows]:
                lines.append(" | ".join(str(v) if v is not None else "" for v in row))
            text = "\n".join(lines).strip()
            return {"extracted_text": text, "truncated_text": text, "metadata": {"headers": headers, "row_count": len(data_rows), "truncated_rows": truncated_rows, "profiled": False}}
        except ImportError:
            return {"extracted_text": "[Excel preview requires pandas or openpyxl]", "truncated_text": "[Excel preview requires pandas or openpyxl]", "metadata": {"headers": [], "row_count": 0, "truncated_rows": 0, "profiled": False}}

    from backend.profiler.dataset_profiler import profile_dataframe

    df = pd.read_excel(io.BytesIO(file_bytes))
    row_count = len(df)
    headers = list(df.columns)

    # Generate statistical profile
    try:
        profile = profile_dataframe(df)
        profile_text = profile.to_prompt_text("")
        profiled = True
    except Exception as exc:
        logger.warning("Excel profiling failed, using truncated text: %s", exc)
        profile_text = None
        profiled = False

    # Build sample text
    sample_rows = min(settings.profile_sample_rows, row_count)
    lines = []
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append("-" * (sum(len(str(h)) for h in headers) + 3 * (len(headers) - 1)))
    for _, row in df.head(sample_rows).iterrows():
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))
    truncated_text = "\n".join(lines).strip()

    result = {
        "extracted_text": truncated_text,
        "truncated_text": truncated_text,
        "metadata": {
            "headers": headers,
            "row_count": row_count,
            "truncated_rows": sample_rows,
            "profiled": profiled,
        },
    }
    if profile_text:
        result["profile_text"] = profile_text
    return result


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
        elif mime_type == EXCEL_MIME_TYPE:
            text_result = _process_excel(file_bytes)
        elif mime_type == "application/pdf":
            text_result = _process_pdf(file_bytes)
        elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            text_result = _process_docx(file_bytes)
        else:
            raise ValueError(f"No parser available for MIME type: {mime_type}")

        file_data["extracted_text"] = text_result["extracted_text"]
        file_data["truncated_text"] = text_result["truncated_text"]
        file_data["metadata"] = text_result["metadata"]
        if "profile_text" in text_result:
            file_data["profile_text"] = text_result["profile_text"]

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


def save_raw_file(user_id: str, file_id: str, filename: str, file_bytes: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload raw file to DO Spaces. Returns the storage key."""
    from backend.services import object_storage
    ext = os.path.splitext(filename)[1].lower()
    key = f"{settings.do_spaces_base_path}/{user_id}/raw/{file_id}{ext}"
    object_storage.upload_bytes(key, file_bytes, content_type)
    logger.debug("Saved raw file %s to key %s", file_id, key)
    return key


def update_file_storage_key(file_id: str, storage_key: str) -> None:
    """Update the Redis-cached file data with the DO Spaces storage key."""
    key = f"{CHAT_FILE_PREFIX}{file_id}"
    data = redis_client.get(key)
    if data:
        file_data = json.loads(data)
        file_data["storage_key"] = storage_key
        ttl = redis_client.ttl(key)
        redis_client.setex(key, max(ttl, 60), json.dumps(file_data))


def get_raw_file(user_id: str, file_id: str) -> Optional[tuple]:
    """
    Download raw file from DO Spaces.

    Returns (file_bytes, ext) where ext is '.csv' or '.xlsx', or None if not found.
    """
    from backend.services import object_storage
    for ext in (".csv", ".xlsx"):
        key = f"{settings.do_spaces_base_path}/{user_id}/raw/{file_id}{ext}"
        data = object_storage.download_bytes(key)
        if data is not None:
            return data, ext
    return None
