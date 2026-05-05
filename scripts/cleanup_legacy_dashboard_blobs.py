#!/usr/bin/env python3
"""Clean up legacy SQLite dashboard blobs from DO Spaces after DataPlane cutover.

This script:
1. Checks cutover percentage via dataplane_cutover_status.py logic
2. Refuses to proceed if < 95% of dashboards are on the new Parquet path
3. Iterates dashboards with cache_key (legacy DO Spaces blob)
4. For each, verifies the DataPlane Parquet cache exists
5. Deletes legacy blob and clears cache_key from database
6. Reports summary

Usage:
    python scripts/cleanup_legacy_dashboard_blobs.py [--dry-run] [--yes]

Options:
    --dry-run    Show what would be deleted without deleting
    --yes        Skip confirmation prompt
"""
import argparse
import os
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(
        description="Clean up legacy SQLite dashboard blobs after DataPlane cutover"
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, ".env"))

    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane
    from backend.services import object_storage

    # Step 1: Check cutover percentage
    cutover_pct = _get_cutover_percentage()
    if cutover_pct < 95.0:
        print(f"Cutover at {cutover_pct:.0f}% — refusing to clean up (need ≥95%)")
        sys.exit(1)

    print(f"Cutover at {cutover_pct:.0f}% — proceeding with cleanup")

    # Step 2: Query dashboards with legacy cache_key
    db = SessionLocal()
    try:
        dashboards = db.query(Dashboard).filter(Dashboard.cache_key.isnot(None)).all()
    except Exception as e:
        print(f"Failed to query dashboards: {e}")
        sys.exit(1)

    if not dashboards:
        print("No dashboards with legacy cache_key found")
        db.close()
        return

    # Step 3: Show what we're about to do
    if args.dry_run:
        print(f"\n[DRY RUN] Would delete {len(dashboards)} legacy blob(s):\n")
    else:
        print(f"\n{len(dashboards)} dashboard(s) to clean up:\n")

    deleted_count = 0
    skipped_count = 0
    failed_count = 0

    if not args.dry_run and not args.yes:
        response = input("Proceed? (y/N) ")
        if response.lower() != "y":
            print("Aborted")
            db.close()
            return

    # Step 4: Iterate dashboards and clean up
    for dash in dashboards:
        print(f"  Dashboard {dash.id} (user {dash.user_id}, cache_key={dash.cache_key[:50]}...)")

        # Get org for user (if available) to determine scope
        try:
            from backend.services.dashboard_cache import _get_org_for_user
            org_id = _get_org_for_user(dash.user_id)
            scope = OwnerScope("org", org_id) if org_id else OwnerScope("user", dash.user_id)
        except Exception:
            scope = OwnerScope("user", dash.user_id)

        # Check if DataPlane Parquet cache exists
        try:
            plane = get_default_plane(scope)
            has_new = _check_new_path(plane, scope, dash.id)
        except Exception as e:
            print(f"    WARNING: Failed to check DataPlane cache: {e}")
            has_new = False

        if not has_new:
            print(f"    SKIP: No DataPlane Parquet cache found for dashboard")
            skipped_count += 1
            continue

        # Delete legacy blob
        if args.dry_run:
            print(f"    DELETE: {dash.cache_key}")
            deleted_count += 1
        else:
            try:
                object_storage.delete_object(dash.cache_key)
                dash.cache_key = None
                db.add(dash)
                db.commit()
                print(f"    DELETED: {dash.cache_key}")
                deleted_count += 1
            except Exception as e:
                print(f"    FAILED: {e}")
                failed_count += 1
                db.rollback()

    db.close()

    # Step 5: Report summary
    print(f"\nCleanup Summary")
    print("-" * 50)
    print(f"  Deleted:    {deleted_count}")
    print(f"  Skipped:    {skipped_count}")
    print(f"  Failed:     {failed_count}")
    if args.dry_run:
        print("\n[DRY RUN] No changes made")


def _get_cutover_percentage() -> float:
    """Calculate % of dashboards on new DataPlane path."""
    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard

    db = SessionLocal()
    try:
        query = db.query(Dashboard)
        dashboards = query.all()
        total = len(dashboards)

        if total == 0:
            return 100.0

        new_path_count = sum(1 for dash in dashboards if _check_new_path_simple(dash))
        both_count = sum(
            1 for dash in dashboards
            if _check_new_path_simple(dash) and _check_legacy_path(dash)
        )

        # Cutover complete % = (new_path_only + both) / total
        return 100.0 * (new_path_count + both_count) / total
    finally:
        db.close()


def _check_new_path_simple(dash) -> bool:
    """Check if dashboard has Parquet cache on DataPlane."""
    try:
        from backend.services.dashboard_cache import _get_org_for_user
        from backend.data_plane.scope import OwnerScope
        from backend.services.data_plane_service import get_default_plane

        org_id = _get_org_for_user(dash.user_id)
        scope = OwnerScope("org", org_id) if org_id else OwnerScope("user", dash.user_id)
        plane = get_default_plane(scope)
        tables = plane.list_tables(scope)
        return any(t.startswith(f"_dash_{dash.id}__") for t in tables)
    except Exception:
        return False


def _check_new_path(plane, scope, dash_id) -> bool:
    """Check if dashboard has Parquet cache on DataPlane (plane already loaded)."""
    try:
        tables = plane.list_tables(scope)
        return any(t.startswith(f"_dash_{dash_id}__") for t in tables)
    except Exception:
        return False


def _check_legacy_path(dash) -> bool:
    """Check if dashboard still has legacy SQLite blob."""
    if not dash.cache_key:
        return False
    try:
        from backend.services import object_storage
        return object_storage.object_exists(dash.cache_key)
    except Exception:
        return False


if __name__ == "__main__":
    main()
