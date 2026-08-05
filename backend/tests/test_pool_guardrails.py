"""Guardrails against the two failure modes that took prod down under load.

1. A connector reused across N items must not stay poisoned after one item
   fails. dashboard_cache and profiling_tasks both loop a single connector over
   many widgets/tables; without a rollback the first failure leaves the
   transaction ABORTED and every later query dies with 25P02.
2. Pool exhaustion must shed load as a 503, not surface as a 500.

Both are self-contained — no database, no running stack.
"""

import sqlite3

import pytest

from backend.connectors.base import BaseConnector, QueryResult


class _CountingConn:
    """Delegating proxy that counts rollback() — sqlite3.Connection.rollback
    is read-only, so it cannot be patched in place."""

    def __init__(self, conn):
        self._conn = conn
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1
        return self._conn.rollback()

    def __getattr__(self, name):
        return getattr(self._conn, name)


class _SqliteProbeConnector(BaseConnector):
    """Minimal concrete BaseConnector over an in-memory sqlite db.

    Only exists to exercise execute_query's transaction handling; the real
    connectors differ solely in how they hand back a connection/cursor.
    """

    _db_type_name = "sqlite"
    _quote_char = '"'

    def __init__(self):
        self._search_path = None
        raw = sqlite3.connect(":memory:")
        raw.isolation_level = ""  # explicit txns, like psycopg2
        cur = raw.cursor()
        cur.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, name TEXT)")
        cur.execute("INSERT INTO t VALUES (1, 'alice'), (2, 'bob')")
        raw.commit()
        cur.close()
        self._connection = _CountingConn(raw)

    def _get_connection(self):
        return self._connection

    def _get_cursor(self, conn, dict_mode: bool = False):
        return conn.cursor()

    # Remaining abstract members. Unused here because _get_connection is
    # overridden to hand back the already-open in-memory connection.
    def _create_connection(self, **kwargs):  # pragma: no cover
        return self._connection

    def _is_connection_alive(self, conn) -> bool:  # pragma: no cover
        return True

    def _get_connect_kwargs(self) -> dict:  # pragma: no cover
        return {}


@pytest.fixture
def connector():
    c = _SqliteProbeConnector()
    yield c
    c._connection.close()


def test_successful_query_ends_its_transaction(connector):
    """A read leaves no open transaction behind.

    On a real Postgres the SET TRANSACTION READ ONLY / SELECT opens one, and
    leaving it open pins a customer-DB backend `idle in transaction` holding an
    MVCC snapshot for the connector's whole lifetime.
    """
    result = connector.execute_query("SELECT id, name FROM t ORDER BY id")

    assert isinstance(result, QueryResult)
    assert result.row_count == 2
    assert connector._connection.rollbacks == 1, (
        "execute_query must end the transaction it opened"
    )
    assert connector._connection.in_transaction is False


def test_failed_query_also_ends_its_transaction(connector):
    """The regression this guards: one bad widget must not kill the rest.

    On Postgres a failed statement leaves the transaction ABORTED, so without a
    rollback every later execute_query on the same connector dies with 25P02 —
    one malformed widget blanks an entire dashboard (dashboard_cache and
    profiling_tasks both loop a single connector over many items).

    The assertion is on the rollback itself, not on a following query
    succeeding: sqlite does *not* abort the transaction on statement error, so
    a "next query still works" check passes here even with the fix reverted.
    The rollback count is the engine-independent part of the mechanism.
    """
    with pytest.raises(Exception):
        connector.execute_query("SELECT * FROM table_that_does_not_exist")

    assert connector._connection.rollbacks == 1, (
        "a failed query must still end its transaction, or Postgres leaves it "
        "ABORTED and poisons every later query on this connector"
    )

    # And the connector is genuinely reusable afterwards.
    result = connector.execute_query("SELECT id FROM t ORDER BY id")
    assert result.row_count == 2
    assert connector._connection.in_transaction is False


def test_driver_exception_class_is_preserved(connector):
    """execute_query used to re-raise everything as a bare Exception.

    That erased the class, so callers could not tell a syntax error from a
    permission error from a dropped connection, and no retry logic was possible.
    """
    with pytest.raises(sqlite3.OperationalError):
        connector.execute_query("SELECT * FROM table_that_does_not_exist")


def test_oversized_raster_is_rejected_before_decode(monkeypatch):
    """A small file can be a huge raster; the pixel count is what OOMs the pod.

    The limit is lowered rather than building a real 169 Mpx image, which would
    allocate the half-gigabyte this check exists to prevent. Callers map
    ValueError to 400 (api/chat_files.py:197).
    """
    import io

    from PIL import Image

    from backend.services import chat_file_service

    monkeypatch.setattr(chat_file_service, "MAX_IMAGE_PIXELS", 100)

    buf = io.BytesIO()
    Image.new("RGB", (50, 50)).save(buf, format="PNG")  # 2500 px > 100

    with pytest.raises(ValueError, match="too large"):
        chat_file_service._process_image(buf.getvalue(), "image/png")

    # Under the limit still works, i.e. the guard is not rejecting everything.
    monkeypatch.setattr(chat_file_service, "MAX_IMAGE_PIXELS", 40_000_000)
    result = chat_file_service._process_image(buf.getvalue(), "image/png")
    assert result["metadata"] == {"width": 50, "height": 50, "format": "PNG"}
    assert result["base64_data"].startswith("data:image/png;base64,")


def test_pool_exhaustion_sheds_as_503():
    """QueuePool timeout must become a 503 + Retry-After, never a 500.

    Exercises the handler directly: importing backend.main pulls in the whole
    app (Qdrant, plugins, settings), which this assertion does not need.
    """
    import asyncio

    from sqlalchemy.exc import TimeoutError as SQLTimeoutError

    from backend.main import _pool_exhausted_handler

    response = asyncio.run(
        _pool_exhausted_handler(None, SQLTimeoutError("QueuePool limit reached"))
    )

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert b"db_pool_exhausted" in response.body
