"""create icps table

Revision ID: 0001_create_icps
Revises:
Create Date: 2026-10-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_icps"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "icps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("brief_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("segments_count", sa.Integer, nullable=False, server_default="0"),
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
    op.create_index("ix_icps_tenant_brief", "icps", ["tenant_id", "brief_id"])
    op.create_index(
        "ix_icps_tenant_brief_version", "icps", ["tenant_id", "brief_id", "version"], unique=True
    )
    op.create_index("ix_icps_tenant_active", "icps", ["tenant_id", "is_active"])
    op.create_index("ix_icps_tenant_created", "icps", ["tenant_id", "created_at"])
    op.execute("CREATE INDEX ix_icps_payload_gin ON icps USING gin (payload jsonb_path_ops)")

    op.execute("ALTER TABLE icps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE icps FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY icps_tenant_isolation ON icps
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS icps_tenant_isolation ON icps")
    op.drop_index("ix_icps_payload_gin", table_name="icps")
    op.drop_index("ix_icps_tenant_created", table_name="icps")
    op.drop_index("ix_icps_tenant_active", table_name="icps")
    op.drop_index("ix_icps_tenant_brief_version", table_name="icps")
    op.drop_index("ix_icps_tenant_brief", table_name="icps")
    op.drop_table("icps")
