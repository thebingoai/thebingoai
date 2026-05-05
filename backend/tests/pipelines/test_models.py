"""Tests for Pipeline model + fingerprint."""
import pytest
from backend.pipelines.runner import compute_pipeline_fingerprint


def test_fingerprint_is_stable():
    """Same inputs → same fingerprint."""
    fp1 = compute_pipeline_fingerprint("facebook_ads:12345", {"since": "2024-01-01", "level": "ad"})
    fp2 = compute_pipeline_fingerprint("facebook_ads:12345", {"since": "2024-01-01", "level": "ad"})
    assert fp1 == fp2


def test_fingerprint_is_64_chars():
    fp = compute_pipeline_fingerprint("conn1", {})
    assert len(fp) == 64


def test_fingerprint_differs_on_config_change():
    fp1 = compute_pipeline_fingerprint("conn1", {"a": 1})
    fp2 = compute_pipeline_fingerprint("conn1", {"a": 2})
    assert fp1 != fp2


def test_fingerprint_differs_on_connection_change():
    fp1 = compute_pipeline_fingerprint("conn1", {"a": 1})
    fp2 = compute_pipeline_fingerprint("conn2", {"a": 1})
    assert fp1 != fp2


def test_fingerprint_none_connection():
    """None connection fingerprint is allowed (falls back to empty string)."""
    fp = compute_pipeline_fingerprint(None, {})
    assert len(fp) == 64


def test_fingerprint_canonical_json_key_order():
    """Key order in extraction_config dict should NOT affect fingerprint."""
    fp1 = compute_pipeline_fingerprint("c", {"b": 2, "a": 1})
    fp2 = compute_pipeline_fingerprint("c", {"a": 1, "b": 2})
    assert fp1 == fp2
