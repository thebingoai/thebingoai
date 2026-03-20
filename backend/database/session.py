from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import sessionmaker, Session
from backend.config import settings


# Detect if using Supabase connection pooler (port 6543).
# Supabase's PgBouncer handles pooling, so we use NullPool to avoid
# double-pooling which causes connection issues.
if ":6543/" in settings.database_url:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        poolclass=NullPool,
        echo=settings.log_level == "DEBUG",
    )
else:
    engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        echo=settings.log_level == "DEBUG",
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """FastAPI dependency for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
