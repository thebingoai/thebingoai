"""Shared SQLite-connector utilities.

Currently houses the read-only query validator used by ``SqliteFileConnector``
(community core) and the ``FacebookAdsSQLiteConnector`` /
``NotionSQLiteConnector`` plugin connectors. All three only allow SELECT/WITH
statements over local SQLite caches; the validator is identical across them.
"""
from __future__ import annotations

import re

MAX_QUERY_LENGTH = 10_000

_DANGEROUS_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER",
    "TRUNCATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "COPY", "LOAD", "SET", "CALL", "RENAME",
    "INTO", "EXPLAIN", "VACUUM", "REINDEX", "CLUSTER",
    "COMMENT", "NOTIFY", "LISTEN", "UNLISTEN", "DO",
    "PREPARE", "DEALLOCATE",
)

_DANGEROUS_FUNCTION_PATTERNS = (
    r"\bload_extension\b",
    r"\breadfile\b",
    r"\bwritefile\b",
)


def validate_readonly_query(query: str) -> None:
    """Raise ``ValueError`` if ``query`` is not a single, read-only SELECT/WITH.

    Strips line/block comments and quoted strings before keyword scanning so
    column names like ``"cluster"`` don't trip the dangerous-keyword list.
    Rejects multi-statement queries, queries longer than ``MAX_QUERY_LENGTH``,
    and any DDL/DML/admin keywords or SQLite filesystem functions
    (``load_extension``, ``readfile``, ``writefile``).
    """
    if len(query) > MAX_QUERY_LENGTH:
        raise ValueError(
            f"Query exceeds maximum allowed length of {MAX_QUERY_LENGTH:,} characters."
        )

    query_upper = query.strip().upper()
    lines = [line.split("--")[0] for line in query_upper.split("\n")]
    query_clean = " ".join(lines)
    query_clean = re.sub(r"/\*.*?\*/", " ", query_clean, flags=re.DOTALL)
    query_clean = " ".join(query_clean.split())

    if ";" in query_clean.rstrip(";"):
        raise ValueError(
            "Multiple statements not allowed. Only single SELECT queries permitted."
        )

    query_for_keyword_check = re.sub(r'"[^"]*"', " ", query_clean)
    query_for_keyword_check = re.sub(r"'[^']*'", " ", query_for_keyword_check)

    for keyword in _DANGEROUS_KEYWORDS:
        if re.search(rf"\b{keyword}\b", query_for_keyword_check):
            raise ValueError(
                f"Query contains forbidden keyword: {keyword}. Only SELECT queries are allowed."
            )

    for pattern in _DANGEROUS_FUNCTION_PATTERNS:
        if re.search(pattern, query_clean, flags=re.IGNORECASE):
            raise ValueError("Query contains a forbidden SQLite function.")

    if not re.match(r"^(SELECT|WITH)\b", query_clean):
        raise ValueError("Query must start with SELECT or WITH (for CTEs)")
