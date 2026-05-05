#!/usr/bin/env python3
"""Pre-migration inventory: enumerate every legacy DO Spaces SQLite blob.

Writes do_spaces_legacy_inventory.json in the current directory.
Safe to re-run — read-only, idempotent.

Usage:
    python scripts/inventory_legacy_do_spaces.py
    python scripts/inventory_legacy_do_spaces.py --prefix custom/path/
    python scripts/inventory_legacy_do_spaces.py --out /tmp/inventory.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, REPO_ROOT)


def main():
    parser = argparse.ArgumentParser(description="Inventory legacy DO Spaces SQLite blobs")
    parser.add_argument("--prefix", default="", help="Only enumerate objects under this prefix")
    parser.add_argument("--out", default="do_spaces_legacy_inventory.json", help="Output file path")
    args = parser.parse_args()

    from dotenv import load_dotenv
    load_dotenv(os.path.join(REPO_ROOT, ".env"))

    from backend.config import settings
    from backend.services.object_storage import ObjectStorageClient

    client = ObjectStorageClient(
        endpoint_url=settings.do_spaces_endpoint,
        region_name=settings.do_spaces_region,
        access_key_id=settings.do_spaces_key_id,
        secret_access_key=settings.do_spaces_secret_key,
        bucket=settings.do_spaces_bucket,
    )

    prefix = args.prefix or getattr(settings, "do_spaces_base_path", "")
    print(f"Enumerating objects in {settings.do_spaces_bucket!r} under prefix {prefix!r} …")

    objects = client.list_objects(prefix=prefix)
    sqlite_objects = [o for o in objects if o["key"].endswith(".sqlite")]

    inventory = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bucket": settings.do_spaces_bucket,
        "prefix": prefix,
        "total_objects": len(objects),
        "sqlite_objects": len(sqlite_objects),
        "objects": sqlite_objects,
    }

    with open(args.out, "w") as f:
        json.dump(inventory, f, indent=2)

    print(f"Found {len(sqlite_objects)} SQLite blob(s) out of {len(objects)} total object(s).")
    print(f"Inventory written to {args.out}")


if __name__ == "__main__":
    main()
