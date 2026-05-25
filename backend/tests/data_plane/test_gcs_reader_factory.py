"""Tests for get_gcs_duckdb_reader — the residency/HMAC-aware reader factory (2a/2e)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import backend.services.data_plane_service as dps
from backend.config import settings
from backend.data_plane.gcs_duckdb import GCSDuckDBReader
from backend.data_plane.scope import OwnerScope


def _row(**kw):
    base = dict(type="google_cloud_project", residency_locked=False, managed_by="bingo")
    base.update(kw)
    return SimpleNamespace(**base)


@pytest.fixture
def hmac(monkeypatch):
    monkeypatch.setattr(settings, "internal_gcs_hmac_key_id", "GOOGKEY", raising=False)
    monkeypatch.setattr(settings, "internal_gcs_hmac_secret", "sec", raising=False)


@pytest.fixture
def fake_plane(monkeypatch):
    monkeypatch.setattr(dps, "_instantiate", lambda row: SimpleNamespace(bucket="bingo_org_x"))


def _reader(monkeypatch, row):
    monkeypatch.setattr(dps, "_resolve_default_row", lambda scope, db: row)
    return dps.get_gcs_duckdb_reader(OwnerScope("org", "o1"), db=MagicMock())


def test_happy_path_returns_reader(monkeypatch, hmac, fake_plane):
    reader = _reader(monkeypatch, _row())
    assert isinstance(reader, GCSDuckDBReader)
    assert reader._bucket == "bingo_org_x"


def test_residency_locked_returns_none(monkeypatch, hmac, fake_plane):
    assert _reader(monkeypatch, _row(residency_locked=True)) is None


def test_customer_managed_returns_none(monkeypatch, hmac, fake_plane):
    assert _reader(monkeypatch, _row(managed_by="customer")) is None


def test_non_gcp_plane_returns_none(monkeypatch, hmac, fake_plane):
    assert _reader(monkeypatch, _row(type="local_filesystem")) is None


def test_no_row_returns_none(monkeypatch, hmac, fake_plane):
    assert _reader(monkeypatch, None) is None


def test_missing_hmac_returns_none(monkeypatch, fake_plane):
    monkeypatch.setattr(settings, "internal_gcs_hmac_key_id", None, raising=False)
    monkeypatch.setattr(settings, "internal_gcs_hmac_secret", None, raising=False)
    assert _reader(monkeypatch, _row()) is None
