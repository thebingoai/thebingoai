"""Tests for backend.governance.contract (Phase G v0 + v1.a)."""
import pytest

from backend.auth.system_context import system_context
from backend.governance import contract as gov


@pytest.fixture(autouse=True)
def _reset_governance_state():
    """Each test starts with the no-op default + zero listeners."""
    gov.reset_check()
    gov.reset_listeners()
    yield
    gov.reset_check()
    gov.reset_listeners()


# ---------------------------------------------------------------------------
# v0 contract: check, register_check, system_context bypass
# ---------------------------------------------------------------------------

def test_default_check_permits_everything():
    assert gov.check(user=object(), action="anything", resource={}) is True


def test_register_check_overrides_default():
    def deny_all(*, user, action, resource):
        return False

    gov.register_check(deny_all)
    assert gov.check(user=object(), action="create", resource={}) is False


def test_system_context_bypasses_registered_check():
    def always_deny(*, user, action, resource):
        return False

    gov.register_check(always_deny)
    assert gov.check(user=object(), action="anything", resource={}) is False
    with system_context("test.bypass"):
        assert gov.check(user=object(), action="anything", resource={}) is True
    assert gov.check(user=object(), action="anything", resource={}) is False


# ---------------------------------------------------------------------------
# v0 lifecycle: org_created
# ---------------------------------------------------------------------------

def test_emit_org_created_with_no_listeners_is_noop():
    gov.emit_org_created(org=object(), creator_user=object())


def test_register_org_created_listener_idempotent():
    calls = []

    def listener(*, org, creator_user):
        calls.append((org, creator_user))

    gov.register_org_created_listener(listener)
    gov.register_org_created_listener(listener)
    gov.emit_org_created(org="o1", creator_user="u1")
    assert calls == [("o1", "u1")]


def test_org_listener_exceptions_are_swallowed():
    calls = []

    def boom(*, org, creator_user):
        raise RuntimeError("listener bug")

    def good(*, org, creator_user):
        calls.append(org)

    gov.register_org_created_listener(boom)
    gov.register_org_created_listener(good)
    gov.emit_org_created(org="o1", creator_user="u1")
    assert calls == ["o1"]


# ---------------------------------------------------------------------------
# v1.a: require() guard
# ---------------------------------------------------------------------------

def test_require_passes_when_check_permits():
    gov.require(user=object(), action="create", resource={"type": "connection"})


def test_require_raises_403_when_check_denies():
    def deny_all(*, user, action, resource):
        return False

    gov.register_check(deny_all)
    # HTTPException is the FastAPI 403; lazy-imported inside require()
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as excinfo:
        gov.require(user=object(), action="create", resource={"type": "connection"})
    assert excinfo.value.status_code == 403
    assert "create" in excinfo.value.detail


def test_require_passes_under_system_context_even_when_denied():
    def deny_all(*, user, action, resource):
        return False

    gov.register_check(deny_all)
    with system_context("background.task"):
        gov.require(user=object(), action="anything", resource={})


# ---------------------------------------------------------------------------
# v1.a: resource_created lifecycle
# ---------------------------------------------------------------------------

def test_emit_resource_created_no_listeners_noop():
    gov.emit_resource_created(resource_type="connection", resource=object(), creator_user=object())


def test_register_resource_created_listener_idempotent():
    calls = []

    def listener(*, resource_type, resource, creator_user):
        calls.append((resource_type, resource, creator_user))

    gov.register_resource_created_listener(listener)
    gov.register_resource_created_listener(listener)
    gov.emit_resource_created(resource_type="pipeline", resource="p1", creator_user="u1")
    assert calls == [("pipeline", "p1", "u1")]


def test_resource_listener_exceptions_are_swallowed():
    calls = []

    def boom(*, resource_type, resource, creator_user):
        raise RuntimeError("listener bug")

    def good(*, resource_type, resource, creator_user):
        calls.append(resource_type)

    gov.register_resource_created_listener(boom)
    gov.register_resource_created_listener(good)
    gov.emit_resource_created(resource_type="dbt_model", resource="m1", creator_user="u1")
    assert calls == ["dbt_model"]


def test_reset_listeners_clears_both_registries():
    def org_listener(*, org, creator_user): ...
    def resource_listener(*, resource_type, resource, creator_user): ...

    gov.register_org_created_listener(org_listener)
    gov.register_resource_created_listener(resource_listener)
    gov.reset_listeners()

    # After reset, both emit calls should fire zero listeners (no errors).
    gov.emit_org_created(org="o", creator_user="u")
    gov.emit_resource_created(resource_type="x", resource="r", creator_user="u")
