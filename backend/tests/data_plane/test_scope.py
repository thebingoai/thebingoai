"""Tests for OwnerScope."""
import pytest
from backend.data_plane.scope import OwnerScope


def test_construction_user():
    s = OwnerScope("user", "42")
    assert s.kind == "user"
    assert s.id == "42"


def test_construction_org():
    s = OwnerScope("org", "abc-uuid")
    assert s.kind == "org"


def test_invalid_kind_raises():
    with pytest.raises(ValueError, match="kind"):
        OwnerScope("workspace", "1")


def test_as_path_user():
    assert OwnerScope("user", "42").as_path() == "user/42"


def test_as_path_org():
    assert OwnerScope("org", "abc").as_path() == "org/abc"


def test_equality():
    a = OwnerScope("user", "42")
    b = OwnerScope("user", "42")
    assert a == b


def test_hash_equality():
    a = OwnerScope("org", "abc")
    b = OwnerScope("org", "abc")
    assert hash(a) == hash(b)
    assert {a, b} == {a}


def test_different_ids_not_equal():
    assert OwnerScope("user", "1") != OwnerScope("user", "2")


def test_immutable():
    s = OwnerScope("user", "1")
    with pytest.raises(AttributeError):
        s.kind = "org"


def test_from_connection_org():
    class FakeConn:
        org_id = "org-uuid"
        user_id = "user-uuid"
        owner_scope_kind = None

    scope = OwnerScope.from_connection(FakeConn())
    assert scope.kind == "org"
    assert scope.id == "org-uuid"


def test_from_connection_user_fallback():
    class FakeConn:
        org_id = None
        user_id = "user-uuid"
        owner_scope_kind = None

    scope = OwnerScope.from_connection(FakeConn())
    assert scope.kind == "user"
    assert scope.id == "user-uuid"


def test_from_connection_uses_explicit_columns():
    class FakeConn:
        org_id = "org-uuid"
        user_id = "user-uuid"
        owner_scope_kind = "user"
        owner_scope_id = "user-uuid"

    scope = OwnerScope.from_connection(FakeConn())
    assert scope.kind == "user"
