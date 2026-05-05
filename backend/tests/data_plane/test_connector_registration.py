"""Tests for ConnectorRegistration.default_scope_hint + fingerprint."""
import pytest
from backend.connectors.factory import _CONNECTORS


class FakeConn:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.mark.parametrize("type_id,expected_scope", [
    ("postgres", "org"),
    ("mysql", "org"),
])
def test_scope_hint(type_id, expected_scope):
    reg = _CONNECTORS[type_id]
    assert reg.default_scope_hint == expected_scope


def test_postgres_fingerprint():
    reg = _CONNECTORS["postgres"]
    conn = FakeConn(host="db.example.com", port=5432, database="mydb")
    assert reg.fingerprint(conn) == "postgres:db.example.com:5432/mydb"


def test_mysql_fingerprint():
    reg = _CONNECTORS["mysql"]
    conn = FakeConn(host="db.example.com", port=3306, database="mydb")
    assert reg.fingerprint(conn) == "mysql:db.example.com:3306/mydb"


def test_postgres_fingerprint_deterministic():
    reg = _CONNECTORS["postgres"]
    conn = FakeConn(host="h", port=5432, database="d")
    assert reg.fingerprint(conn) == reg.fingerprint(conn)


def test_postgres_fingerprint_different_hosts():
    reg = _CONNECTORS["postgres"]
    a = FakeConn(host="host-a", port=5432, database="d")
    b = FakeConn(host="host-b", port=5432, database="d")
    assert reg.fingerprint(a) != reg.fingerprint(b)


def test_sqlite_scope_hint_default():
    # sqlite was registered before Phase 1 — default_scope_hint should be "user"
    reg = _CONNECTORS["sqlite"]
    assert reg.default_scope_hint == "user"


def test_data_plane_registered():
    assert "data_plane" in _CONNECTORS
    assert _CONNECTORS["data_plane"].default_scope_hint == "org"
