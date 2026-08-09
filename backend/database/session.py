from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings


# A client-side pool is kept even behind a transaction-mode pooler
# (Supabase :6543, DO :25061). The pooler multiplexes server connections;
# the client pool keeps TCP+TLS warm so requests don't pay a full handshake
# per query. NullPool here caused a connection storm under load: every
# request opened a fresh TLS connection, saturating the database
# (40 concurrent users -> minutes-long request queues, ROLLBACKs stuck >100s).
# Double-pooling is safe because the ORM relies on no session state
# (no server-side prepared statements, SET vars, or advisory locks).
# pool_pre_ping only protects against a dead connection if the ping itself can
# fail. libpq has no read deadline of its own, so on a half-open socket its
# SELECT 1 blocks for the OS TCP timeout — minutes. That is not a slow query
# anyone can see: it is a synchronous call on the asyncio loop, and with
# UVICORN_WORKERS=1 it freezes the entire worker, /health included, until the
# liveness probe kills the pod (2026-07-23, 84s; 2026-08-06, 323s, both lost
# in-flight chat turns).
#
# Two different kernel timers are involved, and only one of them is keepalives:
#
#   Idle in the pool. Nothing in flight, so the keepalive timer runs: ~10s idle
#   then 3 probes at 5s. A peer reaped on the far side is torn down in ~25s,
#   long before anyone checks the connection out, so pre-ping fails fast and
#   discards it. This is the common case and keepalives cover it.
#
#   Dead with data outstanding. Once SELECT 1 is transmitted the connection is
#   no longer idle, so the keepalive timer never fires — retransmission governs,
#   and on Linux that runs to tcp_retries2, ~15 minutes. Keepalives are not a
#   deadline here at all, which is exactly the frame both incidents hung in
#   (323s is a retransmission backoff, not a 25s keepalive budget).
#
# tcp_user_timeout is the second timer: it bounds how long transmitted data may
# stay unacknowledged before the kernel aborts the connection, so it covers the
# case keepalives structurally cannot. Held equal to the keepalive budget so the
# two cannot drift apart. It does not threaten a legitimately slow query — a
# client waiting on a reply has nothing unacknowledged outstanding.
#
# A module constant rather than an inline literal: create_engine captures
# connect_args in a closure, so this is the only way the settings stay
# readable — by a test, and by anyone debugging a stall.
_KEEPALIVE_IDLE_S = 10
_KEEPALIVE_INTERVAL_S = 5
_KEEPALIVE_COUNT = 3
_DEAD_PEER_BUDGET_S = _KEEPALIVE_IDLE_S + _KEEPALIVE_INTERVAL_S * _KEEPALIVE_COUNT

CONNECT_ARGS = {
    "connect_timeout": settings.db_connect_timeout,
    "keepalives": 1,
    "keepalives_idle": _KEEPALIVE_IDLE_S,
    "keepalives_interval": _KEEPALIVE_INTERVAL_S,
    "keepalives_count": _KEEPALIVE_COUNT,
    "tcp_user_timeout": _DEAD_PEER_BUDGET_S * 1000,  # libpq wants milliseconds
}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    # SQLAlchemy's default is 30s. A saturated pool then stalls each waiter for
    # half a minute while it still holds every other resource it acquired,
    # which turns contention into a pile-up. Fail fast and let the 503 handler
    # in main.py shed load instead.
    pool_timeout=settings.db_pool_timeout,
    # 1800s outlived the pooler: connections idled long enough to be reaped on
    # the far side while the client still believed in them, and the next
    # checkout inherited a half-open socket. 300s recycles well inside that.
    pool_recycle=300,
    connect_args=CONNECT_ARGS,
    echo=settings.log_level == "DEBUG",
)

# Pool pressure tracing. Off by default; DB_POOL_TRACE=true turns it on. The
# cluster has no metrics-server, so this is the only visibility into whether
# the client pool or the PgBouncer server pool is the thing running out.
# Two signals: demand exceeded pool_size, and a checkout held far too long
# (usually a session kept open across network I/O rather than a slow query).
if settings.db_pool_trace:
    import logging
    import time
    from sqlalchemy import event

    _pool_log = logging.getLogger("backend.db.pool")

    @event.listens_for(engine, "checkout")
    def _trace_checkout(dbapi_conn, conn_record, conn_proxy):
        conn_record.info["checkout_at"] = time.monotonic()
        # overflow() > 0, not checkedout() >= pool_size: the latter is true for
        # every checkout while the pool is merely full, which under load is a
        # log line per request. Overflow means demand actually exceeded
        # pool_size — rare, and the number worth waking up for.
        if engine.pool.overflow() > 0:
            _pool_log.warning("pool in overflow: %s", engine.pool.status())

    @event.listens_for(engine, "checkin")
    def _trace_checkin(dbapi_conn, conn_record):
        started = conn_record.info.pop("checkout_at", None)
        if started is None:
            return
        held_ms = (time.monotonic() - started) * 1000
        if held_ms >= settings.db_pool_trace_slow_ms:
            _pool_log.warning(
                "checkout held %.0fms | %s", held_ms, engine.pool.status()
            )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# expire_on_commit=False: chat.py / websocket.py hand ORM rows (history Messages,
# custom agents, skills) to the orchestrator and close the session before the run
# (see the comment there). With the default True, add_message()'s commit blanks
# those rows, and the first attribute read inside the agent — on a now-detached
# instance — raises DetachedInstanceError. Scoped to those two handlers: everywhere
# else wants the default, where a commit invalidates the identity map so the next
# read sees the database rather than a stale in-memory value.
DetachedReadSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, expire_on_commit=False, bind=engine
)


def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_detached_read_db() -> Session:
    """FastAPI dependency for handlers that read ORM rows after closing the session."""
    db = DetachedReadSessionLocal()
    try:
        yield db
    finally:
        db.close()


def end_read_transaction(db: Session) -> None:
    """End an open read transaction while leaving loaded rows usable as-is.

    Behind a transaction-mode pooler the scarce resource is the *server* slot,
    which is released at transaction end even though the client checkout stays.
    So a session that has only read should end its transaction before anything
    slow — a network call to a customer database, an LLM, GCS — rather than
    pinning a slot for the request's whole wall-clock lifetime.

    A bare commit() or rollback() does end the transaction, but it also expires
    every mapped attribute in the identity map, so the next `obj.x` read issues
    a refresh SELECT — which opens a *new* transaction and takes back exactly
    the slot we were freeing. Suppressing expiry for this one commit ends the
    transaction and leaves the already-loaded rows readable, with no extra
    query.

    The session is otherwise unchanged: instances stay attached, so a handler
    that mutates one and commits still persists. expire_on_commit is restored
    so later commits keep default semantics.
    """
    previous = db.expire_on_commit
    db.expire_on_commit = False
    try:
        db.commit()
    finally:
        db.expire_on_commit = previous
