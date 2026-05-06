"""Tests for DbtModel + DbtRun model definitions."""
import pytest
from backend.models.transforms import DbtModel, DbtRun
from backend.transforms.api import TransformCreate


def test_transform_create_incremental_requires_unique_key():
    """incremental materialization must have unique_key."""
    with pytest.raises(Exception):
        TransformCreate(
            name="my_model",
            sql="SELECT 1",
            materialization="incremental",
            unique_key=None,
            owner_scope_kind="user",
            owner_scope_id="user-1",
        )


def test_transform_create_incremental_with_unique_key():
    """incremental + unique_key is valid."""
    t = TransformCreate(
        name="my_model",
        sql="SELECT 1",
        materialization="incremental",
        unique_key="id",
        owner_scope_kind="user",
        owner_scope_id="user-1",
    )
    assert t.materialization == "incremental"
    assert t.unique_key == "id"


def test_transform_create_invalid_materialization():
    """Unknown materialization type should fail validation."""
    with pytest.raises(Exception):
        TransformCreate(
            name="my_model",
            sql="SELECT 1",
            materialization="invalid_type",
            owner_scope_kind="user",
            owner_scope_id="user-1",
        )


def test_transform_create_table_defaults():
    """Table materialization is the default, no unique_key required."""
    t = TransformCreate(
        name="my_model",
        sql="SELECT * FROM my_pipeline",
        owner_scope_kind="org",
        owner_scope_id="org-uuid-1",
    )
    assert t.materialization == "table"
    assert t.unique_key is None
