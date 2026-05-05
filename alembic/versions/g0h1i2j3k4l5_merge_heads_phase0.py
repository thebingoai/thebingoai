"""Merge migration heads after Phase 0 — preflight.

Revision ID: g0h1i2j3k4l5
Revises: a1c2n3u4u5d6, f1e0a7b3c5d9
Create Date: 2026-05-05 17:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "g0h1i2j3k4l5"
down_revision = ("a1c2n3u4u5d6", "f1e0a7b3c5d9")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
