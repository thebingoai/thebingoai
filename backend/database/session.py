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
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_recycle=1800,
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
