"""create experiments table

Revision ID: 0001_create_experiments
Revises:
Create Date: 2026-10-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_experiments"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hypothesis", sa.Text, nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("segment_id", sa.String(36), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False, server_default="email"),
        sa.Column("icp_version", sa.Integer, nullable=True),
        sa.Column("variable_type", sa.String(32), nullable=False),
        sa.Column("variable_description", sa.Text, nullable=False, server_default=""),
        sa.Column("variants", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("sample_size_target", sa.Integer, nullable=False, server_default="200"),
        sa.Column("sample_size_per_variant", sa.Integer, nullable=False, server_default="100"),
        sa.Column("confidence_level", sa.Float, nullable=False, server_default="0.95"),
        sa.Column("minimum_detectable_effect", sa.Float, nullable=False, server_default="0.05"),
        sa.Column("results", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("decision", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint("uq_experiments_tenant_name", "experiments", ["tenant_id", "name"])
    op.create_index("ix_experiments_tenant_status", "experiments", ["tenant_id", "status"])
    op.create_index("ix_experiments_tenant_segment", "experiments", ["tenant_id", "segment_id"])

    op.execute("ALTER TABLE experiments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE experiments FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY experiments_tenant_isolation ON experiments
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS experiments_tenant_isolation ON experiments")
    op.drop_table("experiments")
