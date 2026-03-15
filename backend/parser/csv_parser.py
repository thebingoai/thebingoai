import csv
import io
import logging

logger = logging.getLogger(__name__)


def extract_text(file_bytes: bytes) -> dict:
    """
    Extract text from a CSV file.

    Args:
        file_bytes: Raw bytes of the CSV file

    Returns:
        dict with keys:
            - text: Human-readable formatted representation of the CSV data
            - headers: List of column header names
            - row_count: Number of data rows (excluding the header row)
    """
    content = file_bytes.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(content))

    headers = reader.fieldnames or []
    rows = list(reader)
    row_count = len(rows)

    lines = []

    # Header line
    if headers:
        lines.append(" | ".join(str(h) for h in headers))
        lines.append("-" * (sum(len(str(h)) for h in headers) + 3 * (len(headers) - 1)))

    # Data rows
    for row in rows:
        lines.append(" | ".join(str(row.get(h, "")) for h in headers))

    text = "\n".join(lines).strip()

    return {
        "text": text,
        "headers": list(headers),
        "row_count": row_count,
    }
