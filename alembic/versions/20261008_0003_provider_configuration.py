"""Add safe provider/model configuration and immutable audit history.

Revision ID: 20261008_0003
Revises: 20261006_0002
Create Date: 2026-10-08
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261008_0003"
down_revision = "20261006_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create configuration records without persisting credential values."""
    op.create_table(
        "provider_configurations",
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("credential_reference", sa.String(length=160), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider_id"),
    )
    op.create_table(
        "workflow_model_configurations",
        sa.Column("workflow_id", sa.String(length=80), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["provider_configurations.provider_id"]),
        sa.PrimaryKeyConstraint("workflow_id"),
    )
    op.create_table(
        "configuration_audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=False),
        sa.Column("actor", sa.String(length=80), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_configuration_audit_events_occurred_at", "configuration_audit_events", ["occurred_at"])


def downgrade() -> None:
    """Remove Phase 4.3 configuration records in dependency order."""
    op.drop_index("ix_configuration_audit_events_occurred_at", table_name="configuration_audit_events")
    op.drop_table("configuration_audit_events")
    op.drop_table("workflow_model_configurations")
    op.drop_table("provider_configurations")
