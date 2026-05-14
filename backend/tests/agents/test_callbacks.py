"""Tests for the plugin-registered callback registry."""
import logging

import pytest
from langchain_core.callbacks import BaseCallbackHandler

from backend.agents import callbacks as cb_mod


class _Sentinel(BaseCallbackHandler):
    def __init__(self, tag: str) -> None:
        self.tag = tag


@pytest.fixture(autouse=True)
def _reset_registry():
    cb_mod._factories.clear()
    yield
    cb_mod._factories.clear()


def test_empty_registry_returns_empty_list():
    assert cb_mod.get_callbacks(agent_type="x") == []


def test_register_then_get_returns_handler():
    h = _Sentinel("one")
    cb_mod.register_callback_factory(lambda **_: h)
    out = cb_mod.get_callbacks(agent_type="x")
    assert out == [h]


def test_factory_returning_none_is_skipped():
    cb_mod.register_callback_factory(lambda **_: None)
    assert cb_mod.get_callbacks(agent_type="x") == []


def test_factory_returning_list_is_flattened():
    a, b = _Sentinel("a"), _Sentinel("b")
    cb_mod.register_callback_factory(lambda **_: [a, b])
    assert cb_mod.get_callbacks(agent_type="x") == [a, b]


def test_multiple_factories_compose_in_order():
    a, b = _Sentinel("a"), _Sentinel("b")
    cb_mod.register_callback_factory(lambda **_: a)
    cb_mod.register_callback_factory(lambda **_: b)
    assert cb_mod.get_callbacks(agent_type="x") == [a, b]


def test_factory_raising_is_logged_and_skipped(caplog):
    a = _Sentinel("a")

    def _bad(**_):
        raise RuntimeError("boom")

    cb_mod.register_callback_factory(_bad)
    cb_mod.register_callback_factory(lambda **_: a)
    with caplog.at_level(logging.WARNING):
        out = cb_mod.get_callbacks(agent_type="x")
    assert out == [a]
    assert any("boom" in r.message for r in caplog.records)


def test_factory_receives_kwargs():
    captured: dict = {}

    def _spy(**ctx):
        captured.update(ctx)
        return None

    cb_mod.register_callback_factory(_spy)
    cb_mod.get_callbacks(agent_type="orchestrator", session_id="s1", user_id="u1")
    assert captured == {"agent_type": "orchestrator", "session_id": "s1", "user_id": "u1"}
