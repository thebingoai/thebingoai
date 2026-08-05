"""Seed the shared Airbnb sample connection.

One canonical Parquet copy owned by a fixed system "Samples" org, surfaced
read-only to every user. Replaces the old per-user SQLite seeding — see
`ensure_shared_sample`. Per-user seeding (`seed_sample_connections`) is now a
no-op kept only so its signup-time caller stays untouched.
"""

import logging
import os
from datetime import datetime

from sqlalchemy import and_
from sqlalchemy.orm import Session

from backend.models.database_connection import DatabaseConnection

logger = logging.getLogger(__name__)

SAMPLE_DB_PATH = "/app/data/sample/airbnb_listings.sqlite"
SAMPLE_SOURCE_MARKER = "__bingo_sample__airbnb_listings"
SAMPLE_CONNECTION_NAME = "Airbnb Listings (Sample)"

# Fixed system scope for the ONE shared sample. Its default DataPlane resolves
# to a Bingo-managed shared bucket (provisioned on first plane resolution under
# lockdown; LocalFilesystemDataPlane in dev). The connection + Parquet are
# created once by `ensure_shared_sample`, then made visible to all users.
SAMPLES_ORG_ID = "00000000-0000-0000-0000-0000000005a3"
SAMPLES_USER_ID = "00000000-0000-0000-0000-0000000005a4"  # sentinel owner (User.user_id NOT NULL)
SAMPLES_USER_EMAIL = "bingo-samples-system@internal.bingo"


def shared_sample_clause():
    """SQLAlchemy predicate matching the shared-sample connection(s).

    OR this into any connection-visibility query so the single shared sample is
    listed/loadable for every user regardless of org. Read authorization is
    handled separately by the governance allowance for SAMPLES_ORG_ID.
    """
    return and_(
        DatabaseConnection.owner_scope_kind == "org",
        DatabaseConnection.owner_scope_id == SAMPLES_ORG_ID,
    )


def readable_connection_clause(user_id):
    """Owner OR shared sample — the predicate for every read-path connection
    lookup. Mutation paths must keep filtering on ownership alone."""
    from sqlalchemy import or_

    return or_(DatabaseConnection.user_id == user_id, shared_sample_clause())


def is_shared_sample(connection) -> bool:
    """True when *connection* is the shared, read-only sample."""
    return (
        getattr(connection, "owner_scope_kind", None) == "org"
        and getattr(connection, "owner_scope_id", None) == SAMPLES_ORG_ID
    )


def shared_sample_ids(db: Session) -> set:
    """Connection ids of the shared sample (usually one). Team connection
    whitelists never list the sample — exempt these ids when filtering."""
    return {r.id for r in db.query(DatabaseConnection.id).filter(shared_sample_clause()).all()}


def seed_sample_connections(user_id: str, db: Session) -> None:
    """Deprecated no-op. The shared sample (`ensure_shared_sample`) replaces the
    old per-user SQLite copy; new users need nothing seeded per-signup."""
    return


def _repoint_widgets(db: Session, *, old_connection_id: int, new_connection_id: int) -> None:
    """Rewrite dashboard widgets referencing *old_connection_id* to
    *new_connection_id* so retiring a sample connection doesn't leave widgets
    pointing at a deleted row. connectionId may be stored as int or str."""
    from sqlalchemy.orm.attributes import flag_modified

    from backend.models.dashboard import Dashboard

    old_ids = {old_connection_id, str(old_connection_id)}
    for dashboard in db.query(Dashboard).all():
        changed = False
        for widget in dashboard.widgets or []:
            ds = widget.get("dataSource")
            if isinstance(ds, dict) and ds.get("connectionId") in old_ids:
                ds["connectionId"] = new_connection_id
                changed = True
        if changed:
            flag_modified(dashboard, "widgets")
            db.add(dashboard)
    db.commit()


_SHARED_SAMPLE_LEASE_KEY = "bingo:shared_sample:lease"
# ponytail: fixed TTL, no renewal. Covers provisioning plus the one-off Parquet
# migration of the sample. If it lapses a second replica can start the same
# idempotent work — wasteful, not corrupting. Add a heartbeat only if that
# actually shows up in logs.
_SHARED_SAMPLE_LEASE_TTL = 900  # seconds


def ensure_shared_sample(db: Session) -> None:
    """Idempotently provision the ONE shared Airbnb sample: system org + sentinel
    user + a `sqlite` connection owned by SAMPLES_ORG_ID, migrated once to
    Parquet on the shared plane via the migration substrate. Post-migration all
    reads reroute to the DataPlane (`SqliteFileConnector.from_connection`).

    Best-effort: called at app startup; a failure here must not block boot.
    """
    if not os.path.isfile(SAMPLE_DB_PATH):
        return

    from sqlalchemy.exc import IntegrityError

    from backend.models.organization import Organization
    from backend.models.user import User
    from backend.services.redis_lease import acquire_lease, release_lease

    # 1. System "Samples" org (required so provision-on-miss can load it).
    #    Fixed-PK inserts race across replicas booting concurrently — absorb
    #    the duplicate-key error instead of aborting provisioning.
    if db.get(Organization, SAMPLES_ORG_ID) is None:
        try:
            db.add(Organization(id=SAMPLES_ORG_ID, name="Bingo Samples"))
            db.commit()
        except IntegrityError:
            db.rollback()

    # 2. Sentinel owner user (DatabaseConnection.user_id is NOT NULL).
    if db.get(User, SAMPLES_USER_ID) is None:
        try:
            db.add(User(
                id=SAMPLES_USER_ID,
                email=SAMPLES_USER_EMAIL,
                auth_provider="system",
                org_id=SAMPLES_ORG_ID,
            ))
            db.commit()
        except IntegrityError:
            db.rollback()

    # Steps 3-8 run under a cross-replica lease so exactly one replica provisions
    # AND migrates: migration_journal.connection_id has no unique constraint, so
    # concurrent replicas racing migrate_connection duplicate the journal row and
    # the materialization work.
    #
    # A Redis lease, not pg_advisory_lock — which is what this shipped with and
    # does not hold on this deployment. See services/redis_lease.py: the lock
    # rides a pooled server session that PgBouncer hands to the next client,
    # who then inherits it and proceeds. Losers skip rather than wait:
    # provisioning is idempotent and re-runs on the next boot anyway.
    lease = acquire_lease(_SHARED_SAMPLE_LEASE_KEY, _SHARED_SAMPLE_LEASE_TTL)
    if lease is None:
        logger.info("Shared sample provisioning held by another replica, skipping")
        return
    try:
        # 3. The single shared connection (idempotent by marker + sentinel
        #    scope). The re-check under the lock makes exactly one row win.
        connection = db.query(DatabaseConnection).filter(
            shared_sample_clause(),
            DatabaseConnection.source_filename == SAMPLE_SOURCE_MARKER,
        ).first()
        if connection is None:
            connection = DatabaseConnection(
                user_id=SAMPLES_USER_ID,
                org_id=SAMPLES_ORG_ID,
                owner_scope_kind="org",
                owner_scope_id=SAMPLES_ORG_ID,
                name=SAMPLE_CONNECTION_NAME,
                db_type="sqlite",
                host="internal",
                port=0,
                database="sqlite",
                username="sqlite",
                source_filename=SAMPLE_SOURCE_MARKER,
                dataset_table_name=SAMPLE_DB_PATH,
            )
            connection.password = "sqlite"
            connection.ssl_ca_cert = None
            db.add(connection)
            db.commit()
            db.refresh(connection)

        # 4. Retire the v1 dataset-type shared connection: repoint widgets built on
        #    it to the sqlite-type connection, then drop it (its csv_<id> parquet is
        #    left orphaned, harmless). Widget SQL is not rewritten — v1 table names
        #    may differ; such widgets surface a query error instead of a dangling
        #    "Connection not found".
        legacy = db.query(DatabaseConnection).filter(
            shared_sample_clause(),
            DatabaseConnection.db_type == "dataset",
        ).first()
        if legacy is not None:
            _repoint_widgets(db, old_connection_id=legacy.id, new_connection_id=connection.id)
            db.delete(legacy)
            db.commit()
            logger.info("Removed v1 dataset-type shared sample (connection id=%s)", legacy.id)

        # 5. Publish schema JSON from the bundled file (agents/UI need columns).
        #    Best-effort: a discovery/save failure must not stop the migration
        #    below — this step re-runs on the next boot.
        if not connection.schema_json_path:
            try:
                from backend.api.sqlite_upload import _discover_sqlite_schema
                from backend.services.schema_discovery import (
                    generate_schema_json, save_schema_file, schema_key_for,
                )
                schema_data = _discover_sqlite_schema(SAMPLE_DB_PATH)
                schema_json = generate_schema_json(
                    connection_id=connection.id,
                    connection_name=connection.name,
                    db_type="sqlite",
                    schema_data=schema_data,
                )
                connection.schema_json_path = save_schema_file(schema_key_for(connection), schema_json)
                connection.schema_generated_at = datetime.utcnow()
                connection.table_count = len(schema_data["table_names"])
                db.commit()
            except Exception:
                db.rollback()
                logger.warning(
                    "Schema discovery failed for shared sample %s", connection.id, exc_info=True,
                )

        # 6. Resolve the shared plane (triggers provision-on-miss under lockdown)
        #    then migrate sqlite → Parquet once. Idempotent: journal
        #    status='migrated' returns "skipped"; a failed journal resets to
        #    pending on the next run.
        from backend.migration.substrate import migrate_connection_with_plane
        result = migrate_connection_with_plane(connection, db=db)
        if result.status == "failed":
            logger.warning("Shared sample migration failed: %s", result.error_message)
            return

        # 8. Retire legacy per-user sample rows (pre-shared-sample seeding
        #    created one SQLite copy per user): repoint their widgets to the
        #    canonical connection, then delete. Only after a successful
        #    migration so upgraded users never lose a working sample. Per-row
        #    best-effort: an FK holder (pipeline, journal) blocks that row's
        #    delete without failing boot. Widget SQL needs no rewrite — legacy
        #    rows expose the identical sqlite schema.
        from backend.models.team_connection_policy import TeamConnectionPolicy
        legacy_rows = db.query(DatabaseConnection).filter(
            DatabaseConnection.source_filename == SAMPLE_SOURCE_MARKER,
            DatabaseConnection.id != connection.id,
        ).all()
        for row in legacy_rows:
            try:
                _repoint_widgets(db, old_connection_id=row.id, new_connection_id=connection.id)
                # Team whitelists never list the sample — drop stale policy rows
                # first or their FK blocks the delete (same as connection DELETE).
                db.query(TeamConnectionPolicy).filter(
                    TeamConnectionPolicy.connection_id == row.id
                ).delete()
                db.delete(row)
                db.commit()
                logger.info("Removed legacy per-user sample connection id=%s", row.id)
            except Exception:
                db.rollback()
                logger.warning(
                    "Could not retire legacy sample connection id=%s", row.id, exc_info=True,
                )

        logger.info(
            "Shared sample ready: connection id=%s status=%s table=%s rows=%s",
            connection.id, result.status, result.new_dataplane_table, result.rows_migrated,
        )
    finally:
        release_lease(_SHARED_SAMPLE_LEASE_KEY, lease)
