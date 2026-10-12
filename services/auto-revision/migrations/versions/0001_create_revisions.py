"""create revisions table

Revision ID: 0001_create_revisions
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_revisions"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(32), nullable=False),
        sa.Column("trigger_context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("template_version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("segment_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("diagnosis", sa.Text, nullable=False, server_default=""),
        sa.Column("proposed_changes", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("proposed_template", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("override_version", sa.String(64), nullable=True),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("llm_model", sa.String(64), nullable=False, server_default=""),
        sa.Column("llm_confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_revisions_tenant_status", "revisions", ["tenant_id", "status"])
    op.create_index("ix_revisions_tenant_template", "revisions", ["tenant_id", "template_id"])
    op.create_index("ix_revisions_tenant_created", "revisions", ["tenant_id", "created_at"])

    op.execute("ALTER TABLE revisions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE revisions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY revisions_tenant_isolation ON revisions
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS revisions_tenant_isolation ON revisions")
    op.drop_table("revisions")
