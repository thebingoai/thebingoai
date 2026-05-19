"""Custom dlt destination that routes Parquet output through the Bingo DataPlane.

Usage inside Pipeline.run():
    dest = make_dataplane_destination(plane, scope, table)
    pipeline = dlt.pipeline(pipeline_name=..., destination=dest)
    pipeline.run(source, table_name=table, write_disposition=...)
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.data_plane.scope import OwnerScope

logger = logging.getLogger(__name__)


def make_dataplane_destination(
    plane,
    scope: "OwnerScope",
    table: str,
    *,
    unique_key: tuple[str, ...] | None = None,
):
    """Return a dlt-compatible destination callable that writes to *plane*.

    dlt custom destinations receive (items, table) calls.  We accumulate items
    into a PyArrow table and flush to the DataPlane on each batch.

    `unique_key` (when set) is forwarded to `plane.write_parquet` so the plane
    can register a bronze external table + silver dedup view per pipeline.
    """
    try:
        import dlt
        import pyarrow as pa

        @dlt.destination(name="dataplane", batch_size=5000)
        def _dataplane_dest(items: list[dict], table: dlt.TTableSchema) -> None:
            if not items:
                return
            table_name_from_dlt = table["name"]
            # Forward dlt's write_disposition so the plane can pick snapshot
            # vs append semantics. runner.py maps pipeline.mode='full' →
            # 'replace' and 'incremental' → 'merge'; treat anything other
            # than 'replace' as append (delta union).
            write_disposition = table.get("write_disposition", "replace")
            mode = "overwrite" if write_disposition == "replace" else "append"
            arrow_tbl = pa.Table.from_pylist(items)
            plane.write_parquet(
                scope, table_name_from_dlt, arrow_tbl,
                mode=mode, unique_key=unique_key,
            )
            logger.debug(
                "dlt_destination: wrote %d rows to DataPlane table %s (mode=%s, unique_key=%s)",
                len(items), table_name_from_dlt, mode, unique_key,
            )

        return _dataplane_dest

    except ImportError:
        raise ImportError(
            "dlt is required for Pipeline runs. "
            "Install it with: pip install 'dlt[parquet]>=0.4'"
        )
