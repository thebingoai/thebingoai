#!/usr/bin/env python3
"""Convert a CSV file into a SQLite database for use as sample data.

Usage:
    python scripts/create_sample_db.py ~/Downloads/listings.csv data/sample/airbnb_listings.sqlite
"""

import os
import re
import sqlite3
import sys

import pandas as pd


def _clean_price(val):
    """Strip '$' and ',' from price strings, return float or None."""
    if pd.isna(val):
        return None
    s = str(val).replace("$", "").replace(",", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _clean_percent(val):
    """Strip '%' from percentage strings, return float or None."""
    if pd.isna(val):
        return None
    s = str(val).replace("%", "").strip()
    try:
        return float(s)
    except ValueError:
        return None


def _clean_bool(val):
    """Convert t/f strings to 1/0 integers."""
    if pd.isna(val):
        return None
    s = str(val).strip().lower()
    if s in ("t", "true", "1"):
        return 1
    if s in ("f", "false", "0"):
        return 0
    return None


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input.csv> <output.sqlite>")
        sys.exit(1)

    csv_path = sys.argv[1]
    sqlite_path = sys.argv[2]

    if not os.path.isfile(csv_path):
        print(f"Error: {csv_path} not found")
        sys.exit(1)

    df = pd.read_csv(csv_path, low_memory=False)
    print(f"Read {len(df)} rows, {len(df.columns)} columns from {csv_path}")

    # --- Clean price columns ---
    price_cols = ["price", "estimated_revenue_l365d"]
    for col in price_cols:
        if col in df.columns:
            df[col] = df[col].apply(_clean_price)

    # --- Clean percentage columns ---
    pct_cols = ["host_response_rate", "host_acceptance_rate"]
    for col in pct_cols:
        if col in df.columns:
            df[col] = df[col].apply(_clean_percent)

    # --- Clean boolean columns ---
    bool_cols = [
        "host_is_superhost", "host_has_profile_pic", "host_identity_verified",
        "has_availability", "instant_bookable",
    ]
    for col in bool_cols:
        if col in df.columns:
            df[col] = df[col].apply(_clean_bool)

    # --- Write to SQLite ---
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    if os.path.exists(sqlite_path):
        os.remove(sqlite_path)

    conn = sqlite3.connect(sqlite_path)
    df.to_sql("listings", conn, index=False, if_exists="replace")
    conn.execute("VACUUM")
    conn.close()

    # Verify
    conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    cursor = conn.execute("SELECT COUNT(*) FROM listings")
    row_count = cursor.fetchone()[0]
    cursor = conn.execute("PRAGMA table_info(listings)")
    col_count = len(cursor.fetchall())
    conn.close()

    size_kb = os.path.getsize(sqlite_path) / 1024
    print(f"Created {sqlite_path}: {row_count} rows, {col_count} columns, {size_kb:.0f} KB")


if __name__ == "__main__":
    main()
