import io
import re
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text
from backend.database.session import engine
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
    Convert a filename stem to a safe PostgreSQL identifier:
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


def create_dataset_table(
    connection_id: int,
    sanitized_name: str,
    columns: list[dict],
    df: pd.DataFrame,
) -> str:
    """
    Create a PostgreSQL table in the datasets schema and bulk insert data.

    Table name: ds_{connection_id}_{sanitized_name}
    Returns: fully qualified name like "datasets.ds_42_myfile"
    """
    schema = settings.dataset_schema
    table_name = f"ds_{connection_id}_{sanitized_name}"
    qualified = f"{schema}.{table_name}"

    _PG_TO_SA = {
        "BIGINT": sa.BigInteger(),
        "DOUBLE PRECISION": sa.Float(),
        "BOOLEAN": sa.Boolean(),
        "TIMESTAMP": sa.DateTime(),
        "TEXT": sa.Text(),
    }
    dtype_map = {c["name"]: _PG_TO_SA.get(c["pg_type"], sa.Text()) for c in columns}

    df = coerce_dataframe(df, columns)

    try:
        with engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            df.to_sql(
                table_name,
                conn,
                schema=schema,
                if_exists="replace",
                index=False,
                dtype=dtype_map,
            )
    except Exception as e:
        logger.warning(
            "Typed insertion failed for %s (%s), retrying with all TEXT columns", qualified, e
        )
        # Reset all columns to TEXT in-place so downstream schema reflects actual types
        for col in columns:
            col["pg_type"] = "TEXT"
        # Convert any coerced non-string columns back to string for TEXT insertion
        for c in columns:
            name = c["name"]
            if name in df.columns and df[name].dtype.kind not in ("O", "U", "S"):
                df[name] = df[name].astype(str).where(df[name].notna(), other=None)
        text_dtype_map = {c["name"]: sa.Text() for c in columns}
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {qualified}"))
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
            df.to_sql(
                table_name,
                conn,
                schema=schema,
                if_exists="replace",
                index=False,
                dtype=text_dtype_map,
            )

    logger.info("Created dataset table %s with %d rows", qualified, len(df))
    return qualified


def generate_dataset_schema(
    connection_id: int,
    name: str,
    table_name: str,
    columns: list[dict],
    row_count: int,
) -> dict:
    """
    Generate schema JSON in the same format as schema_discovery.generate_schema_json.
    """
    schema = settings.dataset_schema
    unqualified = table_name.split(".")[-1] if "." in table_name else table_name

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
            schema: {
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


def drop_dataset_table(table_name: str) -> None:
    """
    Drop a dataset table. Accepts qualified ("datasets.ds_42_foo") or
    unqualified name — always uses the configured datasets schema.
    """
    schema = settings.dataset_schema
    unqualified = table_name.split(".")[-1] if "." in table_name else table_name
    qualified = f"{schema}.{unqualified}"

    try:
        with engine.begin() as conn:
            conn.execute(text(f"DROP TABLE IF EXISTS {qualified}"))
        logger.info("Dropped dataset table %s", qualified)
    except Exception as e:
        logger.error("Failed to drop dataset table %s: %s", qualified, e)
