"""Tests for backend.profiler.dataset_profiler."""

import pandas as pd
import pytest

from backend.profiler.dataset_profiler import (
    DatasetProfile,
    profile_dataframe,
    _classify_column,
    _build_sample_text,
)


def _make_mixed_df():
    """Create a small DataFrame with mixed column types."""
    return pd.DataFrame({
        "id": range(1, 101),
        "name": [f"item_{i}" for i in range(1, 101)],
        "category": ["A"] * 40 + ["B"] * 30 + ["C"] * 20 + ["D"] * 10,
        "price": [10.5 + i * 0.1 for i in range(100)],
        "date": pd.date_range("2023-01-01", periods=100, freq="D"),
        "active": [True] * 60 + [False] * 40,
        "score": list(range(0, 100)),
    })


class TestClassifyColumn:
    def test_numeric(self):
        s = pd.Series([1, 2, 3, 4, 5])
        assert _classify_column(s, 5) == "numeric"

    def test_float(self):
        s = pd.Series([1.1, 2.2, 3.3])
        assert _classify_column(s, 3) == "numeric"

    def test_datetime(self):
        s = pd.to_datetime(pd.Series(["2023-01-01", "2023-01-02", "2023-01-03"]))
        assert _classify_column(s, 3) == "datetime"

    def test_boolean(self):
        s = pd.Series([True, False, True])
        assert _classify_column(s, 3) == "boolean"

    def test_categorical_object(self):
        s = pd.Series(["A", "B", "A", "B", "A", "C"] * 10)
        assert _classify_column(s, 60) == "categorical"

    def test_text_object_high_unique(self):
        s = pd.Series([f"unique_{i}" for i in range(100)])
        assert _classify_column(s, 100) == "text"

    def test_numeric_as_string(self):
        s = pd.Series(["1", "2", "3", "4", "5"])
        assert _classify_column(s, 5) == "numeric"

    def test_all_null(self):
        s = pd.Series([None, None, None])
        assert _classify_column(s, 3) == "text"


class TestProfileDataframe:
    def test_basic_profile(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)

        assert isinstance(profile, DatasetProfile)
        assert profile.row_count == 100
        assert profile.column_count == 7
        assert len(profile.columns) == 7

    def test_column_types_detected(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        type_map = {c.name: c.dtype for c in profile.columns}

        assert type_map["id"] == "numeric"
        assert type_map["price"] == "numeric"
        assert type_map["score"] == "numeric"
        assert type_map["category"] == "categorical"
        assert type_map["date"] == "datetime"
        assert type_map["active"] == "boolean"

    def test_numeric_stats(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        price_col = next(c for c in profile.columns if c.name == "price")

        assert price_col.mean is not None
        assert price_col.median is not None
        assert price_col.std is not None
        assert price_col.min_val is not None
        assert price_col.max_val is not None
        assert price_col.q25 is not None
        assert price_col.q75 is not None
        assert price_col.skewness is not None
        assert price_col.outlier_count is not None
        assert price_col.null_count == 0

    def test_categorical_value_counts(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        cat_col = next(c for c in profile.columns if c.name == "category")

        assert cat_col.value_counts is not None
        assert len(cat_col.value_counts) == 4  # A, B, C, D
        # First should be A with 40 count
        assert cat_col.value_counts[0][0] == "A"
        assert cat_col.value_counts[0][1] == 40

    def test_datetime_range(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        date_col = next(c for c in profile.columns if c.name == "date")

        assert date_col.min_date is not None
        assert date_col.max_date is not None
        assert date_col.date_span_days == 99

    def test_boolean_stats(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        bool_col = next(c for c in profile.columns if c.name == "active")

        assert bool_col.true_count == 60
        assert bool_col.false_count == 40
        assert bool_col.true_pct == 60.0

    def test_correlations(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        # id, price, score are all linearly correlated
        assert len(profile.correlations) > 0
        col_pairs = [(a, b) for a, b, _ in profile.correlations]
        # id and score should be strongly correlated (both 0..99)
        assert any(
            ("id" in pair and "score" in pair)
            for pair in [(a, b) for a, b, _ in profile.correlations]
        )

    def test_null_handling(self):
        df = pd.DataFrame({
            "a": [1, 2, None, 4, None],
            "b": ["x", None, "y", "x", None],
        })
        profile = profile_dataframe(df)
        col_a = next(c for c in profile.columns if c.name == "a")
        assert col_a.null_count == 2
        assert col_a.non_null_count == 3

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        profile = profile_dataframe(df)
        assert profile.row_count == 0
        assert profile.column_count == 0
        assert len(profile.columns) == 0

    def test_single_column(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        profile = profile_dataframe(df)
        assert profile.column_count == 1
        assert len(profile.columns) == 1
        assert profile.correlations == []  # need >= 2 numeric cols


class TestToPromptText:
    def test_contains_expected_sections(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        text = profile.to_prompt_text("test.csv")

        assert "=== Dataset Profile: test.csv ===" in text
        assert "Shape: 100 rows x 7 columns" in text
        assert "## Columns Overview" in text
        assert "## Detailed Column Statistics" in text
        assert "## Sample Data" in text

    def test_numeric_stats_in_output(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        text = profile.to_prompt_text("test.csv")

        assert "Mean:" in text
        assert "Median:" in text
        assert "Std:" in text

    def test_categorical_values_in_output(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        text = profile.to_prompt_text("test.csv")

        assert "Value counts:" in text
        assert "A:" in text

    def test_correlations_in_output(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        text = profile.to_prompt_text("test.csv")

        assert "## Numeric Correlations" in text

    def test_sample_rows_in_output(self):
        df = _make_mixed_df()
        profile = profile_dataframe(df)
        text = profile.to_prompt_text("test.csv")

        assert "## Sample Data" in text
        # Should have header + separator + 5 data rows = 7 lines in sample
        sample_section = text.split("## Sample Data")[1]
        sample_lines = [l for l in sample_section.strip().split("\n") if l.strip()]
        assert len(sample_lines) >= 7  # header label + header + sep + 5 rows


class TestBuildSampleText:
    def test_basic_sample(self):
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        text = _build_sample_text(df, ["a", "b"])
        lines = text.strip().split("\n")
        assert lines[0] == "a | b"
        assert "1 | x" in text

    def test_empty_df(self):
        df = pd.DataFrame()
        text = _build_sample_text(df, [])
        assert text == ""
