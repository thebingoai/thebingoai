#!/usr/bin/env python3
"""Migrate DatabaseConnections with legacy SQLite blobs to DataPlane (Parquet).

Processes connections where dataset_table_name is not NULL, migrating the
SQLite-on-DO-Spaces blob into the configured DataPlane (Parquet) and rewriting
widget SQL references as needed.

Usage:
    python scripts/migrate_datasets_to_dataplane.py
    python scripts/migrate_datasets_to_dataplane.py --dry-run
    python scripts/migrate_datasets_to_dataplane.py --scope user:<user_id>
    python scripts/migrate_datasets_to_dataplane.py --scope org:<org_id>
    python scripts/migrate_datasets_to_dataplane.py --connection-id 42
    python scripts/migrate_datasets_to_dataplane.py --rollback 42
    python scripts/migrate_datasets_to_dataplane.py --batch-size 100 --yes
"""
import argparse
import logging
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_ROOT)


# Configure logging to match reset_user.py style
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Migrate database connections with legacy SQLite blobs to DataPlane"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be migrated without writing anything",
    )
    parser.add_argument(
        "--scope",
        default="all",
        help='Scope filter: "user:<user_id>", "org:<org_id>", or "all" (default "all")',
    )
    parser.add_argument(
        "--connection-id",
        type=int,
        help="Migrate only this specific connection",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Process N connections at a time (default 50)",
    )
    parser.add_argument(
        "--rollback",
        type=int,
        help="Roll back a previously migrated connection (by connection ID)",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt (for automation)",
    )
    parser.add_argument(
        "--mark-flag",
        action="store_true",
        help=(
            "After a successful batch, set the `substrate_migration_complete` "
            "feature flag to true for every Org whose connections were processed. "
            "Phase 5 (legacy code retirement) hard-requires this flag."
        ),
    )
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv(os.path.join(REPO_ROOT, ".env"))

    # Handle rollback case
    if args.rollback is not None:
        return _handle_rollback(args.rollback)

    # Validate scope before accessing DB
    if not _validate_scope(args.scope):
        logger.error(f"✗ Invalid scope: {args.scope!r}")
        logger.error('   Use "all", "user:<id>", or "org:<id>"')
        return 1

    # Normal migration flow
    return _handle_migration(args)


def _handle_rollback(connection_id: int) -> int:
    """Roll back a previously migrated connection."""
    from backend.database.session import SessionLocal
    from backend.migration.substrate import rollback_connection

    logger.info(f"Rolling back connection {connection_id}...")

    with SessionLocal() as db:
        result = rollback_connection(connection_id, db=db)

    if result.status == "rolled_back":
        logger.info(f"✓ Connection {connection_id} rolled back successfully")
        logger.info(f"  Pre-migration dataset_table_name restored from journal")
        return 0
    elif result.status == "no_op":
        logger.warning(f"✗ Connection {connection_id} not eligible for rollback")
        logger.warning(f"  (Journal not found or status is not 'migrated')")
        return 1
    else:  # failed
        logger.error(f"✗ Rollback failed for connection {connection_id}")
        logger.error(f"  {result.error_message}")
        return 1


def _validate_scope(scope: str) -> bool:
    """Validate that scope is in the correct format."""
    if scope == "all":
        return True
    if scope.startswith("user:") and len(scope) > 5:
        return True
    if scope.startswith("org:") and len(scope) > 4:
        return True
    return False


def _handle_migration(args) -> int:
    """Handle the normal migration flow."""
    from backend.database.session import SessionLocal
    from backend.models.database_connection import DatabaseConnection
    from backend.migration.substrate import migrate_connection

    # Collect connections to migrate
    with SessionLocal() as db:
        query = db.query(DatabaseConnection).filter(
            DatabaseConnection.dataset_table_name.isnot(None)
        )

        # Apply scope filter
        if args.scope.startswith("user:"):
            user_id = args.scope[5:]
            query = query.filter(DatabaseConnection.user_id == user_id)
        elif args.scope.startswith("org:"):
            org_id = args.scope[4:]
            query = query.filter(DatabaseConnection.org_id == org_id)

        # Apply connection-id filter if specified
        if args.connection_id is not None:
            query = query.filter(DatabaseConnection.id == args.connection_id)

        connections = query.all()

    if not connections:
        logger.info("No connections to migrate")
        return 0

    # Print summary
    logger.info(f"Found {len(connections)} connection(s) to migrate")
    if args.dry_run:
        logger.info("DRY RUN — no changes will be written")

    # List connections
    for conn in connections:
        scope_label = f"org={conn.org_id}" if conn.org_id else f"user={conn.user_id}"
        logger.info(f"  • Connection {conn.id}: {conn.name} ({scope_label})")

    # Prompt for confirmation (unless --dry-run or --yes)
    if not args.dry_run and not args.yes:
        response = input("\nProceed? [y/N] ")
        if response.lower() != "y":
            logger.info("Cancelled")
            return 0

    # Process in batches
    migrated = 0
    skipped = 0
    widget_review_pending = 0
    failed = 0

    for i in range(0, len(connections), args.batch_size):
        batch = connections[i : i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(connections) + args.batch_size - 1) // args.batch_size

        logger.info(f"\nBatch {batch_num}/{total_batches}:")

        with SessionLocal() as db:
            for conn in batch:
                result = migrate_connection(conn.id, dry_run=args.dry_run, db=db)

                # Log per-connection result
                if result.status == "migrated":
                    logger.info(
                        f"  ✓ Connection {conn.id}: migrated"
                        f" ({result.tables_migrated} table(s), {result.rows_migrated} row(s))"
                    )
                    migrated += 1
                elif result.status == "dry_run":
                    logger.info(
                        f"  ✓ Connection {conn.id}: would migrate"
                        f" ({result.tables_migrated} table(s), {result.rows_migrated} row(s))"
                    )
                    migrated += 1
                elif result.status == "skipped":
                    logger.info(f"  - Connection {conn.id}: skipped")
                    skipped += 1
                elif result.status == "widget_review_pending":
                    logger.warning(
                        f"  ⚠ Connection {conn.id}: migrated but {result.widgets_queued_for_review} widget(s)"
                        f" queued for manual SQL rewrite review"
                    )
                    widget_review_pending += 1
                    migrated += 1
                else:  # failed
                    logger.error(f"  ✗ Connection {conn.id}: {result.error_message}")
                    failed += 1

    # Final summary
    logger.info("\n" + "=" * 60)
    logger.info("Migration Summary")
    logger.info("=" * 60)
    logger.info(f"  Migrated:                     {migrated}")
    logger.info(f"  Skipped:                      {skipped}")
    logger.info(f"  Widgets queued for review:    {widget_review_pending}")
    logger.info(f"  Failed:                       {failed}")
    logger.info("=" * 60)

    # Flip the substrate_migration_complete feature flag for every affected Org
    # so Phase 5 (legacy code retirement) can detect global readiness.
    if args.mark_flag and not args.dry_run and migrated > 0 and failed == 0:
        org_ids = sorted({c.org_id for c in connections if c.org_id})
        if org_ids:
            try:
                from backend.config.feature_flags import set_flag
                for org_id in org_ids:
                    set_flag(org_id, "substrate_migration_complete", True)
                logger.info(
                    "Flagged %d Org(s) with substrate_migration_complete=true",
                    len(org_ids),
                )
            except Exception:
                logger.exception("Failed to set substrate_migration_complete flag")

    # Post-migration check query
    logger.info(
        "\nTo verify migration, run:"
        "\n  SELECT count(*) FROM database_connections WHERE dataset_table_name IS NOT NULL"
    )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
