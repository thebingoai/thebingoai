#!/usr/bin/env python3
"""Post-cutover audit: report per-dashboard DataPlane migration status.

Checks every dashboard in the database. For each one reports whether:
  - It has a Parquet cache on the Org's DataPlane (new path)
  - It still has a legacy SQLite blob on DO Spaces (old path)

Usage:
    python scripts/dataplane_cutover_status.py
    python scripts/dataplane_cutover_status.py --org-id <uuid>
"""
import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(description="DataPlane cutover status audit")
    parser.add_argument("--org-id", default=None, help="Limit to a specific org ID")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, ".env"))

    from backend.database.session import SessionLocal
    from backend.models.dashboard import Dashboard
    from backend.data_plane.scope import OwnerScope
    from backend.services.data_plane_service import get_default_plane
    from backend.services import object_storage

    db = SessionLocal()
    try:
        query = db.query(Dashboard)
        dashboards = query.all()
    finally:
        db.close()

    total = len(dashboards)
    new_path = 0
    legacy_path = 0
    both = 0
    neither = 0

    for dash in dashboards:
        has_new = _check_new_path(dash)
        has_legacy = _check_legacy_path(dash)
        if has_new and has_legacy:
            both += 1
        elif has_new:
            new_path += 1
        elif has_legacy:
            legacy_path += 1
        else:
            neither += 1

    print(f"\nDataPlane Cutover Status ({total} dashboards)")
    print("-" * 50)
    print(f"  Parquet only (new path):      {new_path:>4}  ({_pct(new_path, total):.0f}%)")
    print(f"  SQLite only (legacy):         {legacy_path:>4}  ({_pct(legacy_path, total):.0f}%)")
    print(f"  Both paths (transitional):    {both:>4}  ({_pct(both, total):.0f}%)")
    print(f"  No cache at all:              {neither:>4}  ({_pct(neither, total):.0f}%)")
    print(f"\nCutover complete: {_pct(new_path + both, total):.0f}% on new path")


def _check_new_path(dash) -> bool:
    try:
        from backend.data_plane.scope import OwnerScope
        from backend.services.dashboard_cache import _get_org_for_user
        from backend.services.data_plane_service import get_default_plane

        org_id = _get_org_for_user(dash.user_id)
        scope = OwnerScope("org", org_id) if org_id else OwnerScope("user", dash.user_id)
        plane = get_default_plane(scope)
        tables = plane.list_tables(scope)
        return any(t.startswith(f"_dash_{dash.id}__") for t in tables)
    except Exception:
        return False


def _check_legacy_path(dash) -> bool:
    if not dash.cache_key:
        return False
    try:
        from backend.services import object_storage
        return object_storage.object_exists(dash.cache_key)
    except Exception:
        return False


def _pct(part: int, total: int) -> float:
    return 0.0 if total == 0 else 100.0 * part / total


if __name__ == "__main__":
    main()
