"""Custom dlt destination wrapping the Bingo DataPlane.

Asserts the (destination, row_counter) tuple contract and that the
counter increments per batch -- the counter is the only accurate source of
row counts for PipelineRun.rows_written (dlt LoadPackage exposes file_size,
not rows).
"""
from unittest.mock import MagicMock

import pytest


def _scope():
    from backend.data_plane.scope import OwnerScope
    return OwnerScope("user", "user-1")


def test_make_dataplane_destination_returns_tuple():
    from backend.pipelines.dlt_destination import make_dataplane_destination

    plane = MagicMock()
    dest, counter = make_dataplane_destination(plane, _scope(), "tbl")
    assert dest is not None
    assert counter == {"rows": 0}


def test_row_counter_increments_per_batch():
    """End-to-end via a real dlt pipeline: run a small in-memory resource
    and assert the counter reports the row count, not file size."""
    import dlt
    from backend.pipelines.dlt_destination import make_dataplane_destination

    plane = MagicMock()
    dest, counter = make_dataplane_destination(plane, _scope(), "tbl")

    @dlt.resource(name="tbl", write_disposition="append")
    def rows():
        yield from [{"a": 1}, {"a": 2}, {"a": 3}, {"a": 4}]

    pipeline = dlt.pipeline(pipeline_name="test_row_counter", destination=dest)
    pipeline.run(rows)

    assert counter["rows"] == 4
    # plane.write_parquet called at least once with our rows
    assert plane.write_parquet.called
    # And the write went through with mode='append' (matching write_disposition)
    last_call = plane.write_parquet.call_args
    assert last_call.kwargs["mode"] == "append"


def test_destination_forwards_unique_key():
    """unique_key passed to make_dataplane_destination must reach every
    plane.write_parquet call so the plane can register bronze+view."""
    import dlt
    from backend.pipelines.dlt_destination import make_dataplane_destination

    plane = MagicMock()
    uk = ("event_date", "event_timestamp")
    dest, _ = make_dataplane_destination(plane, _scope(), "tbl", unique_key=uk)

    @dlt.resource(name="tbl", write_disposition="append")
    def rows():
        yield {"a": 1}

    dlt.pipeline(pipeline_name="test_uk_forward", destination=dest).run(rows)
    assert plane.write_parquet.call_args.kwargs["unique_key"] == uk


def test_destination_replace_disposition_maps_to_overwrite():
    """write_disposition='replace' (mode=full backfill) must arrive at the
    plane as mode='overwrite' so it pins the snapshot partition."""
    import dlt
    from backend.pipelines.dlt_destination import make_dataplane_destination

    plane = MagicMock()
    dest, _ = make_dataplane_destination(plane, _scope(), "tbl")

    @dlt.resource(name="tbl", write_disposition="replace")
    def rows():
        yield {"a": 1}

    dlt.pipeline(pipeline_name="test_replace_mode", destination=dest).run(rows)
    assert plane.write_parquet.call_args.kwargs["mode"] == "overwrite"
