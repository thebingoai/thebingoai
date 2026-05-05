"""Tests for backend.auth.system_context (Phase 0 — preflight)."""
import asyncio
import pytest

from backend.auth.system_context import (
    SYSTEM_ACTOR,
    SystemContext,
    current_system_context,
    system_context,
)


def test_no_active_context_returns_none():
    assert current_system_context() is None


def test_context_manager_sets_and_clears():
    assert current_system_context() is None
    with system_context("pipeline.run") as ctx:
        assert isinstance(ctx, SystemContext)
        assert ctx.actor == SYSTEM_ACTOR
        assert ctx.reason == "pipeline.run"
        assert ctx.scope is None
        assert current_system_context() is ctx
    assert current_system_context() is None


def test_context_manager_passes_scope():
    fake_scope = object()
    with system_context("test.scope", scope=fake_scope) as ctx:
        assert ctx.scope is fake_scope


def test_nested_contexts_stack():
    with system_context("outer") as outer:
        assert current_system_context() is outer
        with system_context("inner") as inner:
            assert current_system_context() is inner
        assert current_system_context() is outer
    assert current_system_context() is None


def test_context_clears_on_exception():
    with pytest.raises(RuntimeError):
        with system_context("will.fail"):
            raise RuntimeError("boom")
    assert current_system_context() is None


def test_empty_reason_raises():
    with pytest.raises(ValueError, match="reason"):
        with system_context(""):
            pass


def test_system_context_immutable():
    with system_context("read.only") as ctx:
        with pytest.raises(Exception):
            ctx.reason = "changed"  # frozen dataclass


def test_concurrent_asyncio_tasks_see_independent_stacks():
    results = {}

    async def inner(label: str, reason: str):
        with system_context(reason):
            await asyncio.sleep(0)  # yield to let other task run
            ctx = current_system_context()
            assert ctx is not None
            results[label] = ctx.reason

    async def run():
        await asyncio.gather(
            inner("a", "task.a"),
            inner("b", "task.b"),
        )

    asyncio.run(run())
    assert results == {"a": "task.a", "b": "task.b"}
