"""create campaigns

Revision ID: 0001_create_campaigns
Revises:
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_campaigns"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("start_date", sa.Date, nullable=True),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("goals", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("budget", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("targeting_summary", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("metrics", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("tags", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint("uq_campaigns_tenant_name", "campaigns", ["tenant_id", "name"])
    op.create_index("ix_campaigns_tenant_status", "campaigns", ["tenant_id", "status"])

    op.execute("ALTER TABLE campaigns ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE campaigns FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY campaigns_tenant_isolation ON campaigns
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS campaigns_tenant_isolation ON campaigns")
    op.drop_table("campaigns")
