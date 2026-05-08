"""Tests for backend.governance.contract (Phase G v0)."""
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


def test_listener_exceptions_are_swallowed():
    calls = []

    def boom(*, org, creator_user):
        raise RuntimeError("listener bug")

    def good(*, org, creator_user):
        calls.append(org)

    gov.register_org_created_listener(boom)
    gov.register_org_created_listener(good)
    gov.emit_org_created(org="o1", creator_user="u1")
    assert calls == ["o1"]
