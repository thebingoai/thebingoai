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


def make_dataplane_destination(plane, scope: "OwnerScope", table: str):
    """Return a dlt-compatible destination callable that writes to *plane*.

    dlt custom destinations receive (items, table) calls.  We accumulate items
    into a PyArrow table and flush to the DataPlane on each batch.
    """
    try:
        import dlt
        import pyarrow as pa

        @dlt.destination(name="dataplane", batch_size=5000)
        def _dataplane_dest(items: list[dict], table: dlt.TTableSchema) -> None:
            if not items:
                return
            table_name_from_dlt = table["name"]
            arrow_tbl = pa.Table.from_pylist(items)
            plane.write_parquet(scope, table_name_from_dlt, arrow_tbl, mode="overwrite")
            logger.debug("dlt_destination: wrote %d rows to DataPlane table %s", len(items), table_name_from_dlt)

        return _dataplane_dest

    except ImportError:
        raise ImportError(
            "dlt is required for Pipeline runs. "
            "Install it with: pip install 'dlt[parquet]>=0.4'"
        )
