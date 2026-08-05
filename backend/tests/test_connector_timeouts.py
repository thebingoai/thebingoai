"""Timeout / query-cap behavior for the source-DB connectors.

Covers the PR #148 read-path hardening: bounded connect + read/write timeouts on
the mysql/postgres connectors, and the postgres statement_timeout cap in the
shared BaseConnector.execute_query. No live DB — `_get_connect_kwargs()` is pure,
and the statement_timeout cap is exercised through a recording fake cursor.
"""
from backend.config import settings
from backend.connectors.base import BaseConnector


# ── connect kwargs: bounded timeouts (mysql / postgres) ─────────────────────

def test_mysql_connect_kwargs_bound_timeouts():
    from backend.connectors.mysql import MySQLConnector

    kwargs = MySQLConnector("h", 3306, "d", "u", "p")._get_connect_kwargs()
    # read_timeout now uses the named cap directly — no min(ms//1000, 50) that
    # could collapse to 0 and silently disable the bound.
    assert kwargs["read_timeout"] == settings.source_read_timeout_s
    assert kwargs["connect_timeout"] == settings.source_connect_timeout_s
    assert kwargs["write_timeout"] == settings.source_connect_timeout_s


def test_postgres_connect_kwargs_bound_and_keepalive():
    from backend.connectors.postgres import PostgresConnector

    kwargs = PostgresConnector("h", 5432, "d", "u", "p")._get_connect_kwargs()
    assert kwargs["connect_timeout"] == settings.source_connect_timeout_s
    # Keepalives detect dead idle sockets (managed poolers drop idle conns).
    assert kwargs["keepalives"] == 1
    assert kwargs["keepalives_idle"] == 30
    assert kwargs["keepalives_interval"] == 10
    assert kwargs["keepalives_count"] == 3


def test_postgres_sends_no_options_startup_parameter():
    """`options` is a libpq *startup* parameter. PgBouncer's allow-list is
    client_encoding/datestyle/timezone/standard_conforming_strings/application_name
    — anything else is refused at connect with "unsupported startup parameter",
    so a source DB behind a pooler would fail to open at all. Timeouts on the
    schema path go through SET LOCAL instead (see the row-count tests below)."""
    from backend.connectors.postgres import PostgresConnector

    kwargs = PostgresConnector("h", 5432, "d", "u", "p")._get_connect_kwargs()
    assert "options" not in kwargs


# ── postgres statement_timeout cap (BaseConnector.execute_query) ─────────────

class _RecordingCursor:
    """Minimal cursor that records executed SQL and returns one dummy row."""

    def __init__(self):
        self.executed: list[str] = []
        self.description = [("n",)]

    def execute(self, sql, params=None):
        self.executed.append(sql)

    def fetchmany(self, n):
        return [(1,)]

    def close(self):
        pass


class _FakePGConnector(BaseConnector):
    """Postgres-typed connector with the DB layer stubbed out, so
    execute_query's timeout/read-only preamble runs against a recording cursor."""

    _db_type_name = "PostgreSQL"

    def __init__(self, cursor):
        super().__init__("h", 5432, "d", "u", "p")
        self._cursor = cursor
        self._connection = object()  # non-None → _get_connection returns it as-is

    def _create_connection(self, **kwargs):
        raise AssertionError("must not open a real connection")

    def _is_connection_alive(self, conn):
        return True

    def _get_cursor(self, conn, dict_mode=False):
        return self._cursor

    def _get_connect_kwargs(self):
        return {}


def test_postgres_statement_timeout_capped_under_frontend_limit():
    cur = _RecordingCursor()
    _FakePGConnector(cur).execute_query("SELECT 1")
    # default: min(query_timeout_ms=120000, source_read_timeout_s*1000=50000)
    cap_ms = min(settings.query_timeout_ms, settings.source_read_timeout_s * 1000)
    assert f"SET LOCAL statement_timeout = '{cap_ms}'" in cur.executed
    # read-only preamble still issued (defense-in-depth unchanged by the cap)
    assert "SET TRANSACTION READ ONLY" in cur.executed


def test_statement_timeout_takes_query_timeout_when_lower(monkeypatch):
    # A query_timeout_ms below the read cap must win — proves the min() picks the
    # smaller bound, not a hardcoded ceiling.
    monkeypatch.setattr(settings, "query_timeout_ms", 8000)
    cur = _RecordingCursor()
    _FakePGConnector(cur).execute_query("SELECT 1")
    assert "SET LOCAL statement_timeout = '8000'" in cur.executed


# ── schema path: the COUNT(*) fallback is bounded per-transaction ────────────

class _RowCountCursor:
    """Answers the reltuples probe with `estimate`, then optionally blows up on
    the COUNT(*) the way a statement_timeout abort would."""

    def __init__(self, estimate=0, count_error=None):
        self.executed: list[str] = []
        self._estimate = estimate
        self._count_error = count_error
        self._last = None
        self.connection = self  # _get_row_count reaches for cursor.connection
        self.rollbacks = 0

    def execute(self, sql, params=None):
        self.executed.append(sql)
        if sql.startswith("SELECT COUNT(*)"):
            if self._count_error is not None:
                raise self._count_error
            self._last = (42,)
        elif "reltuples" in sql:
            self._last = (self._estimate,)
        else:
            self._last = None

    def fetchone(self):
        return self._last

    def rollback(self):
        self.rollbacks += 1


def _pg_connector():
    from backend.connectors.postgres import PostgresConnector

    return PostgresConnector("h", 5432, "d", "u", "p")


def test_every_catalog_read_is_capped_per_transaction():
    """The cap covers the whole schema read, not just the COUNT(*): the
    information_schema views behind get_tables/get_table_schema do per-column
    permission checks and degrade with catalog size. SET LOCAL, so it reverts at
    commit and never leaks to the next client on a pooled server connection."""
    cur = _RowCountCursor(estimate=0)
    conn = _pg_connector()
    conn._get_connection = lambda: object()
    conn._get_cursor = lambda _c, dict_mode=False: cur

    conn._schema_cursor()

    assert cur.executed == [
        f"SET LOCAL statement_timeout = '{settings.query_timeout_ms}'"
    ]


def test_the_cap_hook_is_a_no_op_for_engines_without_one():
    """Non-Postgres connectors inherit the base hook and must not gain a stray
    statement."""
    cur = _RowCountCursor(estimate=0)
    from backend.connectors.mysql import MySQLConnector

    conn = MySQLConnector("h", 3306, "d", "u", "p")
    conn._get_connection = lambda: object()
    conn._get_cursor = lambda _c, dict_mode=False: cur

    conn._schema_cursor()

    assert cur.executed == []


def test_row_count_skips_the_scan_when_the_estimate_is_usable():
    cur = _RowCountCursor(estimate=1000)

    assert _pg_connector()._get_row_count(cur, "public", "t") == 1000

    assert not any("COUNT(*)" in sql for sql in cur.executed)


def test_row_count_degrades_and_rolls_back_when_the_scan_is_killed():
    """A timed-out scan leaves the transaction ABORTED; without the rollback
    every later schema query on this connection dies with 25P02."""
    cur = _RowCountCursor(estimate=0, count_error=Exception("canceling statement due to statement timeout"))

    assert _pg_connector()._get_row_count(cur, "public", "t") == 0
    assert cur.rollbacks == 1
