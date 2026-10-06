"""Add immutable execution history for workflow runs.

Revision ID: 20261006_0002
Revises: 20261006_0001
Create Date: 2026-10-06
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261006_0002"
down_revision = "20261006_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create append-only event rows ordered uniquely within each run."""
    op.create_table(
        "run_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("stage_name", sa.String(length=80), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_run_events_sequence"),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])
    op.create_index("ix_run_events_event_type", "run_events", ["event_type"])


def downgrade() -> None:
    """Remove append-only events while retaining run snapshots and stages."""
    op.drop_index("ix_run_events_event_type", table_name="run_events")
    op.drop_index("ix_run_events_run_id", table_name="run_events")
    op.drop_table("run_events")
