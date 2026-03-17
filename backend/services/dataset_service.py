import io
import re
import sqlite3
import tempfile
import pandas as pd
from backend.config import settings
from backend.services.schema_discovery import generate_schema_json, save_schema_file
import logging

logger = logging.getLogger(__name__)


def parse_csv(file_bytes: bytes) -> pd.DataFrame:
    """Parse CSV bytes into a DataFrame."""
    return pd.read_csv(io.BytesIO(file_bytes))


def parse_excel(file_bytes: bytes) -> pd.DataFrame:
    """Parse Excel bytes into a DataFrame."""
    return pd.read_excel(io.BytesIO(file_bytes))


def sanitize_name(name: str) -> str:
    """
    Convert a filename stem to a safe identifier:
    lowercase, non-alphanumeric → underscore, collapse runs,
    strip leading/trailing underscores, truncate to 50 chars.
    """
    name = re.sub(r'[^a-z0-9_]', '_', name.lower())
    name = re.sub(r'_+', '_', name).strip('_')
    if not name:
        name = "dataset"
    return name[:50]


def infer_column_types(df: pd.DataFrame) -> list[dict]:
    """
    Infer PostgreSQL column types from a DataFrame.

    Rules (applied in order per column):
    1. If pandas already inferred integer → BIGINT
    2. If pandas already inferred float → DOUBLE PRECISION
    3. If pandas already inferred bool → BOOLEAN
    4. If pandas already inferred datetime → TIMESTAMP
    5. Try pd.to_numeric(errors='coerce') — if >90% non-null parse:
       INTEGER (no fraction) or DOUBLE PRECISION (has fraction)
    6. Try pd.to_datetime(errors='coerce') — if >80% non-null parse → TIMESTAMP
    7. Check boolean string patterns → BOOLEAN
    8. Fallback → TEXT

    Returns list of {"name", "pg_type", "pandas_dtype"}.
    """
    result = []
    total = len(df)

    for col in df.columns:
        series = df[col]
        pandas_dtype = str(series.dtype)
        pg_type = "TEXT"

        if total == 0:
            result.append({"name": col, "pg_type": pg_type, "pandas_dtype": pandas_dtype})
            continue

        non_null_count = series.notna().sum()

        if pd.api.types.is_integer_dtype(series):
            pg_type = "BIGINT"
        elif pd.api.types.is_float_dtype(series):
            pg_type = "DOUBLE PRECISION"
        elif pd.api.types.is_bool_dtype(series):
            pg_type = "BOOLEAN"
        elif pd.api.types.is_datetime64_any_dtype(series):
            pg_type = "TIMESTAMP"
        else:
            eligible = non_null_count if non_null_count > 0 else 1

            numeric_series = pd.to_numeric(series, errors='coerce')
            numeric_non_null = numeric_series.notna().sum()
            if numeric_non_null / eligible > 0.95:
                has_fraction = ((numeric_series.dropna() % 1) != 0).any()
                pg_type = "DOUBLE PRECISION" if has_fraction else "BIGINT"
            else:
                # Two-stage datetime gate: regex pre-filter then parse threshold
                _DATE_RE = re.compile(
                    r'^\d{4}-\d{1,2}-\d{1,2}'                  # 2024-01-15 (ISO)
                    r'|^\d{4}/\d{1,2}/\d{1,2}'                 # 2024/01/15
                    r'|^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}'        # 01/15/2024, 15-01-2024
                    r'|^[A-Za-z]+ \d{1,2},? \d{4}'            # January 15, 2024
                    r'|^\d{1,2}[- ][A-Za-z]{3,}[- ]\d{2,4}'  # 15 Jan 2024, 15-Jan-24
                    r'|^\d{8}$'                                 # 20240115 (compact ISO)
                )
                str_vals_raw = series.dropna().astype(str).str.strip()
                date_like = str_vals_raw.apply(lambda v: bool(_DATE_RE.match(v))).sum()
                if date_like / eligible > 0.50:
                    dt_series = pd.to_datetime(series, errors='coerce')
                    dt_non_null = dt_series.notna().sum()
                    if dt_non_null / eligible > 0.90:
                        pg_type = "TIMESTAMP"
                if pg_type == "TEXT":
                    bool_vals = {"true", "false", "yes", "no", "1", "0"}
                    str_vals = str_vals_raw.str.lower()
                    if len(str_vals) > 0 and str_vals.isin(bool_vals).all():
                        pg_type = "BOOLEAN"

        result.append({"name": col, "pg_type": pg_type, "pandas_dtype": pandas_dtype})

    return result


def coerce_dataframe(df: pd.DataFrame, columns: list[dict]) -> pd.DataFrame:
    """
    Coerce DataFrame values to match inferred column types before to_sql.
    Non-conforming values become NULL instead of causing insertion errors.
    """
    df = df.copy()
    for col in columns:
        name = col["name"]
        pg_type = col["pg_type"]
        if name not in df.columns:
            continue
        if pg_type in ("BIGINT", "DOUBLE PRECISION"):
            df[name] = pd.to_numeric(df[name], errors='coerce')
        elif pg_type == "TIMESTAMP":
            df[name] = pd.to_datetime(df[name], errors='coerce')
        elif pg_type == "BOOLEAN":
            bool_map = {"true": True, "false": False, "yes": True, "no": False, "1": True, "0": False}
            df[name] = df[name].astype(str).str.strip().str.lower().map(bool_map)
    return df


def create_dataset_sqlite(
    connection_id: int,
    sanitized_name: str,
    columns: list[dict],
    df: pd.DataFrame,
) -> str:
    """
    Create a SQLite database file from the DataFrame.

    Creates a single table named 'data' with type mapping:
    BIGINT→INTEGER, DOUBLE PRECISION→REAL, BOOLEAN→INTEGER (0/1),
    TIMESTAMP→TEXT, TEXT→TEXT.

    Returns: path to the temporary SQLite file.
    """
    _PG_TO_SQLITE = {
        "BIGINT": "INTEGER",
        "DOUBLE PRECISION": "REAL",
        "BOOLEAN": "INTEGER",
        "TIMESTAMP": "TEXT",
        "TEXT": "TEXT",
    }

    # Coerce the dataframe first
    df = coerce_dataframe(df, columns)

    # For TIMESTAMP columns, convert to string since SQLite stores dates as TEXT
    for col in columns:
        name = col["name"]
        if col["pg_type"] == "TIMESTAMP" and name in df.columns:
            df[name] = df[name].astype(str).where(df[name].notna(), other=None)
        elif col["pg_type"] == "BOOLEAN" and name in df.columns:
            # Convert bool to 0/1 integers
            df[name] = df[name].map(lambda v: int(v) if v is not None and not (isinstance(v, float) and pd.isna(v)) else None)

    # Create temp file for the SQLite database
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    sqlite_path = tmp.name

    conn = sqlite3.connect(sqlite_path)
    try:
        # Build CREATE TABLE statement
        col_defs = []
        for col in columns:
            sqlite_type = _PG_TO_SQLITE.get(col["pg_type"], "TEXT")
            col_defs.append(f'"{col["name"]}" {sqlite_type}')
        create_sql = f'CREATE TABLE IF NOT EXISTS "data" ({", ".join(col_defs)})'
        conn.execute(create_sql)
        conn.commit()

        # Write data using pandas
        df.to_sql("data", conn, if_exists="replace", index=False)
        conn.commit()
    finally:
        conn.close()

    logger.info("Created SQLite dataset for connection %s with %d rows", connection_id, len(df))
    return sqlite_path


def generate_dataset_schema(
    connection_id: int,
    name: str,
    table_name: str,
    columns: list[dict],
    row_count: int,
) -> dict:
    """
    Generate schema JSON in the same format as schema_discovery.generate_schema_json.
    Uses 'sqlite' as schema key and 'data' as the table name (SQLite table).
    """
    schema_key = "sqlite"
    unqualified = "data"

    col_list = [
        {
            "name": c["name"],
            "type": c["pg_type"],
            "nullable": True,
            "primary_key": False,
            "foreign_key": None,
        }
        for c in columns
    ]

    schema_data = {
        "schemas": {
            schema_key: {
                "tables": {
                    unqualified: {
                        "row_count": row_count,
                        "columns": col_list,
                    }
                }
            }
        },
        "table_names": [unqualified],
        "relationships": [],
    }

    return generate_schema_json(connection_id, name, "dataset", schema_data)


def delete_dataset_sqlite(do_spaces_key: str) -> None:
    """
    Delete a dataset SQLite file from DO Spaces.
    """
    from backend.services import object_storage
    object_storage.delete_object(do_spaces_key)
