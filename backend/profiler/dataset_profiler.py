"""Statistical dataset profiler for CSV/Excel files uploaded to chat.

Generates a comprehensive profile from a pandas DataFrame, including
per-column statistics, correlations, and a small data sample. The profile
is rendered as structured text for LLM context injection.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

import pandas as pd

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ColumnProfile:
    name: str
    dtype: str  # "numeric", "categorical", "datetime", "boolean", "text"
    total_count: int
    non_null_count: int
    null_count: int
    null_pct: float
    unique_count: int
    # Numeric
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[Any] = None
    max_val: Optional[Any] = None
    q25: Optional[float] = None
    q75: Optional[float] = None
    skewness: Optional[float] = None
    outlier_count: Optional[int] = None
    # Categorical
    value_counts: Optional[List[tuple]] = None  # [(value, count, pct), ...]
    mode_value: Optional[Any] = None
    # Datetime
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    date_span_days: Optional[int] = None
    # Boolean
    true_count: Optional[int] = None
    false_count: Optional[int] = None
    true_pct: Optional[float] = None


@dataclass
class DatasetProfile:
    row_count: int
    column_count: int
    columns: List[ColumnProfile]
    correlations: List[tuple] = field(default_factory=list)  # [(col_a, col_b, r)]
    sample_text: str = ""
    profiled_columns: int = 0
    memory_mb: float = 0.0

    def to_prompt_text(self, filename: str) -> str:
        """Render the full profile as structured text for LLM injection."""
        lines: list[str] = []

        lines.append(f"=== Dataset Profile: {filename} ===")
        lines.append(f"Shape: {_fmt(self.row_count)} rows x {self.column_count} columns")
        lines.append(f"Memory: ~{self.memory_mb:.1f} MB")
        if self.profiled_columns < self.column_count:
            lines.append(f"Note: Only first {self.profiled_columns} of {self.column_count} columns profiled.")
        lines.append("")

        # Columns overview table
        lines.append("## Columns Overview")
        lines.append("| # | Name | Type | Non-Null | Unique |")
        lines.append("|---|------|------|----------|--------|")
        for i, col in enumerate(self.columns, 1):
            nn = f"{_fmt(col.non_null_count)} ({col.null_pct:.1f}% null)" if col.null_count > 0 else f"{_fmt(col.non_null_count)} (100%)"
            lines.append(f"| {i} | {col.name} | {col.dtype} | {nn} | {_fmt(col.unique_count)} |")
        lines.append("")

        # Detailed per-column stats
        lines.append("## Detailed Column Statistics")
        lines.append("")
        for col in self.columns:
            lines.append(f"### {col.name} ({col.dtype})")
            null_info = f"Non-null: {_fmt(col.non_null_count)} ({100 - col.null_pct:.2f}%)"
            if col.null_count > 0:
                null_info += f" | Null: {_fmt(col.null_count)}"
            null_info += f" | Unique: {_fmt(col.unique_count)}"
            lines.append(f"  {null_info}")

            if col.dtype == "numeric":
                lines.append(f"  Mean: {_fmtf(col.mean)} | Median: {_fmtf(col.median)} | Std: {_fmtf(col.std)}")
                lines.append(f"  Min: {_fmtf(col.min_val)} | Q25: {_fmtf(col.q25)} | Q75: {_fmtf(col.q75)} | Max: {_fmtf(col.max_val)}")
                extra = []
                if col.skewness is not None:
                    extra.append(f"Skewness: {col.skewness:.2f}")
                if col.outlier_count is not None:
                    extra.append(f"Outliers: {_fmt(col.outlier_count)} (beyond {settings.profile_outlier_std:.0f}\u03c3)")
                if extra:
                    lines.append(f"  {' | '.join(extra)}")

            elif col.dtype == "categorical":
                if col.mode_value is not None:
                    lines.append(f"  Mode: {col.mode_value}")
                if col.value_counts:
                    lines.append("  Value counts:")
                    for val, count, pct in col.value_counts:
                        lines.append(f"    {val}: {_fmt(count)} ({pct:.1f}%)")

            elif col.dtype == "datetime":
                if col.min_date and col.max_date:
                    span = f" (span: {_fmt(col.date_span_days)} days)" if col.date_span_days is not None else ""
                    lines.append(f"  Range: {col.min_date} to {col.max_date}{span}")

            elif col.dtype == "boolean":
                if col.true_count is not None:
                    lines.append(f"  True: {_fmt(col.true_count)} ({col.true_pct:.1f}%) | False: {_fmt(col.false_count)} ({100 - col.true_pct:.1f}%)")

            lines.append("")

        # Correlations
        if self.correlations:
            lines.append("## Numeric Correlations")
            for col_a, col_b, r in self.correlations:
                lines.append(f"  {col_a} ~ {col_b}: {r:.2f}")
            lines.append("")

        # Sample rows
        if self.sample_text:
            lines.append(f"## Sample Data ({settings.profile_sample_rows} rows)")
            lines.append(self.sample_text)

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profiling functions
# ---------------------------------------------------------------------------

def profile_dataframe(df: pd.DataFrame) -> DatasetProfile:
    """Generate a comprehensive statistical profile from a DataFrame."""
    row_count = len(df)
    column_count = len(df.columns)
    max_cols = settings.profile_max_columns

    cols_to_profile = list(df.columns[:max_cols])
    memory_mb = df.memory_usage(deep=True).sum() / (1024 * 1024)

    column_profiles = []
    for col_name in cols_to_profile:
        series = df[col_name]
        dtype = _classify_column(series, row_count)
        cp = _build_column_profile(col_name, series, dtype, row_count)
        column_profiles.append(cp)

    correlations = _compute_correlations(df[cols_to_profile])
    sample_text = _build_sample_text(df, cols_to_profile)

    return DatasetProfile(
        row_count=row_count,
        column_count=column_count,
        columns=column_profiles,
        correlations=correlations,
        sample_text=sample_text,
        profiled_columns=len(cols_to_profile),
        memory_mb=memory_mb,
    )


def _classify_column(series: pd.Series, row_count: int) -> str:
    """Classify a pandas Series as numeric/categorical/datetime/boolean/text."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    # Object columns: try to detect hidden numerics or datetimes
    if series.dtype == object:
        non_null = series.dropna()
        if len(non_null) == 0:
            return "text"

        # Try numeric conversion
        numeric_converted = pd.to_numeric(non_null, errors="coerce")
        if numeric_converted.notna().sum() / len(non_null) > 0.8:
            return "numeric"

        # Try datetime conversion (sample to avoid slow parsing)
        sample = non_null.head(100)
        try:
            dt_converted = pd.to_datetime(sample, errors="coerce")
            if dt_converted.notna().sum() / len(sample) > 0.8:
                return "datetime"
        except Exception:
            pass

        # Categorical vs text: low unique ratio = categorical
        if row_count > 0 and series.nunique() / row_count < 0.5:
            return "categorical"
        return "text"

    return "text"


def _build_column_profile(
    name: str, series: pd.Series, dtype: str, row_count: int
) -> ColumnProfile:
    """Build a ColumnProfile for a single column."""
    non_null = int(series.notna().sum())
    null_count = row_count - non_null
    null_pct = (null_count / row_count * 100) if row_count > 0 else 0.0
    unique = int(series.nunique())

    cp = ColumnProfile(
        name=name,
        dtype=dtype,
        total_count=row_count,
        non_null_count=non_null,
        null_count=null_count,
        null_pct=null_pct,
        unique_count=unique,
    )

    if dtype == "numeric":
        _fill_numeric(cp, series)
    elif dtype == "categorical":
        _fill_categorical(cp, series, row_count)
    elif dtype == "datetime":
        _fill_datetime(cp, series)
    elif dtype == "boolean":
        _fill_boolean(cp, series, non_null)

    return cp


def _fill_numeric(cp: ColumnProfile, series: pd.Series) -> None:
    """Populate numeric statistics on a ColumnProfile."""
    # Convert object columns that were classified as numeric
    if series.dtype == object:
        series = pd.to_numeric(series, errors="coerce")

    clean = series.dropna()
    if len(clean) == 0:
        return

    desc = clean.describe()
    cp.mean = float(desc.get("mean", 0))
    cp.std = float(desc.get("std", 0))
    cp.min_val = float(desc.get("min", 0))
    cp.q25 = float(desc.get("25%", 0))
    cp.median = float(desc.get("50%", 0))
    cp.q75 = float(desc.get("75%", 0))
    cp.max_val = float(desc.get("max", 0))

    try:
        cp.skewness = float(clean.skew())
    except Exception:
        cp.skewness = None

    # Outlier detection
    if cp.std and cp.std > 0:
        threshold = settings.profile_outlier_std
        outliers = (clean - cp.mean).abs() > threshold * cp.std
        cp.outlier_count = int(outliers.sum())
    else:
        cp.outlier_count = 0


def _fill_categorical(cp: ColumnProfile, series: pd.Series, row_count: int) -> None:
    """Populate categorical statistics on a ColumnProfile."""
    vc = series.value_counts(dropna=True)
    max_cats = settings.profile_max_categories
    top = vc.head(max_cats)

    cp.value_counts = [
        (str(val), int(count), float(count / row_count * 100) if row_count > 0 else 0.0)
        for val, count in top.items()
    ]

    if not vc.empty:
        cp.mode_value = str(vc.index[0])


def _fill_datetime(cp: ColumnProfile, series: pd.Series) -> None:
    """Populate datetime statistics on a ColumnProfile."""
    if series.dtype == object:
        series = pd.to_datetime(series, errors="coerce")

    clean = series.dropna()
    if len(clean) == 0:
        return

    min_dt = clean.min()
    max_dt = clean.max()
    cp.min_date = str(min_dt.date()) if hasattr(min_dt, "date") else str(min_dt)
    cp.max_date = str(max_dt.date()) if hasattr(max_dt, "date") else str(max_dt)
    try:
        cp.date_span_days = (max_dt - min_dt).days
    except Exception:
        cp.date_span_days = None


def _fill_boolean(cp: ColumnProfile, series: pd.Series, non_null: int) -> None:
    """Populate boolean statistics on a ColumnProfile."""
    cp.true_count = int(series.sum())
    cp.false_count = non_null - cp.true_count
    cp.true_pct = float(cp.true_count / non_null * 100) if non_null > 0 else 0.0


def _compute_correlations(df: pd.DataFrame) -> List[tuple]:
    """Compute pairwise Pearson correlations for numeric columns."""
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    max_corr_cols = settings.profile_max_correlation_columns

    if len(numeric_cols) < 2 or len(numeric_cols) > max_corr_cols:
        return []

    try:
        corr_matrix = df[numeric_cols].corr()
    except Exception:
        return []

    threshold = settings.profile_correlation_threshold
    pairs = []
    seen = set()
    for i, col_a in enumerate(numeric_cols):
        for j, col_b in enumerate(numeric_cols):
            if i >= j:
                continue
            r = corr_matrix.loc[col_a, col_b]
            if pd.notna(r) and abs(r) > threshold:
                key = (min(col_a, col_b), max(col_a, col_b))
                if key not in seen:
                    seen.add(key)
                    pairs.append((col_a, col_b, float(r)))

    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs


def _build_sample_text(df: pd.DataFrame, columns: list) -> str:
    """Build a pipe-delimited sample of the first N rows."""
    sample_n = settings.profile_sample_rows
    if len(df) == 0:
        return ""

    sample_df = df[columns].head(sample_n)
    headers = [str(c) for c in columns]
    lines = [" | ".join(headers)]
    lines.append("-" * (sum(len(h) for h in headers) + 3 * (len(headers) - 1)))

    for _, row in sample_df.iterrows():
        lines.append(" | ".join(str(row[c]) for c in columns))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _fmt(n: Any) -> str:
    """Format a number with comma separators."""
    if isinstance(n, (int, float)) and not pd.isna(n):
        if isinstance(n, float) and n == int(n):
            return f"{int(n):,}"
        return f"{n:,}"
    return str(n)


def _fmtf(v: Any) -> str:
    """Format a float to 2 decimal places, or return as-is."""
    if v is None:
        return "N/A"
    if isinstance(v, float):
        if abs(v) >= 1000:
            return f"{v:,.2f}"
        return f"{v:.2f}"
    return str(v)
