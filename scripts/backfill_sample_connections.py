"""Backfill the sample SQLite connection for existing users.

The sample connection is normally seeded at user creation (see
``backend.services.seed.seed_sample_connections``). Accounts created before that
seeding worked have no sample row; this one-off script seeds them.

Idempotent — ``seed_sample_connections`` skips users that already have the row
and no-ops when the sample DB file is absent. Run inside the backend container,
where ``/app/data/sample/airbnb_listings.sqlite`` exists:

    docker exec thebingo-backend python scripts/backfill_sample_connections.py
    docker exec thebingo-backend python scripts/backfill_sample_connections.py --dry-run
"""

import argparse
import os
import sys

# Ensure the community backend is importable when run as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.session import SessionLocal
from backend.models.user import User
from backend.services.seed import (
    SAMPLE_DB_PATH,
    SAMPLE_SOURCE_MARKER,
    seed_sample_connections,
)
from backend.models.database_connection import DatabaseConnection


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List users missing the sample connection without creating it.",
    )
    args = parser.parse_args()

    if not os.path.isfile(SAMPLE_DB_PATH):
        print(f"Sample DB not found at {SAMPLE_DB_PATH} — run inside the backend container.")
        return 1

    db = SessionLocal()
    seeded = 0
    skipped = 0
    try:
        user_ids = [row.id for row in db.query(User.id).all()]
        for uid in user_ids:
            has_sample = (
                db.query(DatabaseConnection.id)
                .filter(
                    DatabaseConnection.user_id == uid,
                    DatabaseConnection.source_filename == SAMPLE_SOURCE_MARKER,
                )
                .first()
                is not None
            )
            if has_sample:
                skipped += 1
                continue
            if args.dry_run:
                print(f"[dry-run] would seed sample for user {uid}")
                seeded += 1
                continue
            seed_sample_connections(uid, db)
            seeded += 1

        verb = "would seed" if args.dry_run else "seeded"
        print(f"{verb} {seeded} user(s); {skipped} already had the sample connection.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
