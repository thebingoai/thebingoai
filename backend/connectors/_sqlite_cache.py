"""Shared SQLite blob caching for legacy connectors.

Downloads a SQLite database file from object storage, caches it locally with
a 1-hour TTL, and atomically replaces the cached file. Used by
``SqliteFileConnector`` (community core) and the FacebookAds and Notion plugin
connectors during the DO Spaces → DataPlane migration window. To be removed
once all SQLite-blob-cached connectors migrate to the DataPlane.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 3600


def download_and_cache_sqlite_blob(
    connection,
    *,
    cache_dir: str,
    db_session=None,
    missing_blob_message: Optional[str] = None,
) -> str:
    """Return a local path to the SQLite file for ``connection``.

    Looks up ``connection.dataset_table_name`` as the object-storage key.
    If the local cache file exists and is younger than ``CACHE_TTL_SECONDS``,
    its path is returned. Otherwise the blob is downloaded from object
    storage, written to a temp file, and atomically renamed into place.

    When ``connection.dataset_table_name`` is an absolute filesystem path
    pointing to an existing file (e.g. bundled sample data), it is returned
    directly with no caching.

    On a missing blob, ``connection.health_status`` is set to ``"unhealthy"``
    when ``db_session`` is provided, then ``FileNotFoundError`` is raised.
    ``missing_blob_message`` lets callers customize the "still syncing"
    error string when ``connection.dataset_table_name`` is None.
    """
    do_spaces_key = connection.dataset_table_name

    if do_spaces_key is None:
        raise FileNotFoundError(
            missing_blob_message
            or f"SQLite file not found for connection {connection.id}: dataset_table_name is None."
        )

    if os.path.isabs(do_spaces_key) and os.path.isfile(do_spaces_key):
        return do_spaces_key

    from backend.services import object_storage

    cache_path = os.path.join(cache_dir, f"{connection.id}.sqlite")

    cache_valid = (
        os.path.exists(cache_path)
        and os.path.getmtime(cache_path) > time.time() - CACHE_TTL_SECONDS
    )
    if cache_valid:
        return cache_path

    data = object_storage.download_bytes(do_spaces_key)
    if data is None:
        if db_session is not None:
            from datetime import datetime, timezone
            connection.health_status = "unhealthy"
            connection.health_checked_at = datetime.now(timezone.utc)
            db_session.commit()
        raise FileNotFoundError(
            f"SQLite file not found in DO Spaces: {do_spaces_key}"
        )

    os.makedirs(cache_dir, exist_ok=True)
    tmp_path = cache_path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.rename(tmp_path, cache_path)
    return cache_path
