"""Tests for GAP-2f: post-write warm enqueue (debounced)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import backend.tasks.dashboard_refresh_tasks as drt
from backend.data_plane.scope import OwnerScope
from backend.services import dashboard_cache as dc


def _widget(sql):
    return {"dataSource": {"sql": sql}}


def _patch_db(monkeypatch, dashboards):
    fake_db = MagicMock()
    fake_db.query.return_value.filter.return_value.all.return_value = dashboards
    cm = MagicMock()
    cm.__enter__.return_value = fake_db
    cm.__exit__.return_value = False
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: cm)


def _patch_redis(monkeypatch, exists=False):
    fake_r = MagicMock()
    fake_r.exists.return_value = exists
    monkeypatch.setattr("redis.from_url", lambda url: fake_r)
    return fake_r


def test_enqueues_only_backed_dashboards(monkeypatch):
    d1 = SimpleNamespace(id=1, widgets=[_widget("SELECT * FROM csv_5")])
    d2 = SimpleNamespace(id=2, widgets=[_widget("SELECT * FROM other_t")])
    _patch_db(monkeypatch, [d1, d2])
    _patch_redis(monkeypatch, exists=False)
    delay = MagicMock()
    monkeypatch.setattr(drt.execute_dashboard_refresh, "delay", delay)

    n = dc.enqueue_dashboard_warm_for_table(OwnerScope("user", "u1"), "csv_5")
    assert n == 1
    delay.assert_called_once_with(1)


def test_debounce_skips_recently_warmed(monkeypatch):
    d1 = SimpleNamespace(id=1, widgets=[_widget("SELECT * FROM csv_5")])
    _patch_db(monkeypatch, [d1])
    _patch_redis(monkeypatch, exists=True)  # rate-limit key present → debounced
    delay = MagicMock()
    monkeypatch.setattr(drt.execute_dashboard_refresh, "delay", delay)

    n = dc.enqueue_dashboard_warm_for_table(OwnerScope("user", "u1"), "csv_5")
    assert n == 0
    delay.assert_not_called()


def test_never_raises_on_failure(monkeypatch):
    # SessionLocal blows up → helper swallows and returns 0.
    monkeypatch.setattr("backend.database.session.SessionLocal", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    assert dc.enqueue_dashboard_warm_for_table(OwnerScope("org", "o1"), "csv_5") == 0
