"""Tests for the cron_dispatcher helper."""
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest
import sys

# Import the module directly to avoid backend.tasks.__init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "cron_dispatcher",
    "/Users/edmundhee/Work/GitHub/gruda/bingo-enterprise/bingo/backend/tasks/cron_dispatcher.py"
)
cron_dispatcher = importlib.util.module_from_spec(spec)
sys.modules["cron_dispatcher"] = cron_dispatcher
spec.loader.exec_module(cron_dispatcher)

dispatch_due_rows = cron_dispatcher.dispatch_due_rows


class ColumnDescriptor:
    """SQLAlchemy-style column descriptor for tests."""
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return MagicMock()

    def __le__(self, other):
        return MagicMock()

    def __getattr__(self, name):
        return MagicMock()


class FakeModelMeta(type):
    """Metaclass to create proper column descriptors."""
    def __new__(mcs, name, bases, dct):
        # Add column descriptors for ORM-like behavior
        for col_name in ['enabled', 'cron_expression', 'next_run_at']:
            if col_name not in dct:
                dct[col_name] = ColumnDescriptor(col_name)
        return super().__new__(mcs, name, bases, dct)


class FakeModel(metaclass=FakeModelMeta):
    def __init__(self, id, enabled, cron_expression, next_run_at):
        self.id = id
        # Instance attributes override class descriptors
        self.__dict__['enabled'] = enabled
        self.__dict__['cron_expression'] = cron_expression
        self.__dict__['next_run_at'] = next_run_at


def _make_db(rows):
    """Create a mock database session with query support."""
    db = MagicMock()
    # Mock the query chain: db.query(Model).filter(...).all()
    query_mock = MagicMock()
    filter_mock = MagicMock()

    db.query.return_value = query_mock
    query_mock.filter.return_value = filter_mock
    filter_mock.all.return_value = rows

    return db


def test_dispatch_due_rows_calls_dispatch_fn():
    now = datetime(2024, 1, 1, 12, 0)
    row = FakeModel("r1", True, "* * * * *", now)
    db = _make_db([row])
    dispatched = []
    count = dispatch_due_rows(
        db,
        model_cls=FakeModel,
        enabled_field="enabled",
        cron_field="cron_expression",
        next_run_field="next_run_at",
        dispatch_fn=lambda r: dispatched.append(r.id),
        now=now,
    )
    assert count == 1
    assert "r1" in dispatched


def test_dispatch_no_due_rows_returns_zero():
    db = _make_db([])
    count = dispatch_due_rows(
        db,
        model_cls=FakeModel,
        enabled_field="enabled",
        cron_field="cron_expression",
        next_run_field="next_run_at",
        dispatch_fn=lambda r: None,
        now=datetime(2024, 1, 1),
    )
    assert count == 0


def test_dispatch_advances_next_run_at():
    now = datetime(2024, 1, 1, 12, 0)
    row = FakeModel("r1", True, "0 * * * *", now)
    db = _make_db([row])
    dispatch_due_rows(
        db,
        model_cls=FakeModel,
        enabled_field="enabled",
        cron_field="cron_expression",
        next_run_field="next_run_at",
        dispatch_fn=lambda r: None,
        now=now,
    )
    # next_run_at should be advanced past now
    assert row.next_run_at > now


def test_dispatch_fn_exception_does_not_halt_other_rows():
    now = datetime(2024, 1, 1, 12, 0)
    row1 = FakeModel("r1", True, "* * * * *", now)
    row2 = FakeModel("r2", True, "* * * * *", now)
    db = _make_db([row1, row2])
    dispatched = []

    def _dispatch(r):
        if r.id == "r1":
            raise RuntimeError("simulated error")
        dispatched.append(r.id)

    count = dispatch_due_rows(
        db,
        model_cls=FakeModel,
        enabled_field="enabled",
        cron_field="cron_expression",
        next_run_field="next_run_at",
        dispatch_fn=_dispatch,
        now=now,
    )
    # r2 should still be dispatched even though r1 raised
    assert "r2" in dispatched
