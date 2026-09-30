"""create briefs table

Revision ID: 0001_create_briefs
Revises:
Create Date: 2026-09-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_briefs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "briefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("completeness_score", sa.Float, nullable=False, server_default="0"),
        sa.Column("raw_input", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("qa_history", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("identity", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("offering", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("targeting_hints", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("outreach_goals", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("missing_info", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_briefs_tenant_id", "briefs", ["tenant_id"])
    op.create_index("ix_briefs_status", "briefs", ["status"])
    op.create_index("ix_briefs_tenant_status", "briefs", ["tenant_id", "status"])
    op.create_index("ix_briefs_tenant_created", "briefs", ["tenant_id", "created_at"])

    op.execute("CREATE INDEX ix_briefs_identity_gin ON briefs USING gin (identity jsonb_path_ops)")
    op.execute("CREATE INDEX ix_briefs_offering_gin ON briefs USING gin (offering jsonb_path_ops)")

    op.execute("ALTER TABLE briefs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE briefs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY briefs_tenant_isolation ON briefs
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS briefs_tenant_isolation ON briefs")
    op.drop_index("ix_briefs_offering_gin", table_name="briefs")
    op.drop_index("ix_briefs_identity_gin", table_name="briefs")
    op.drop_index("ix_briefs_tenant_created", table_name="briefs")
    op.drop_index("ix_briefs_tenant_status", table_name="briefs")
    op.drop_index("ix_briefs_status", table_name="briefs")
    op.drop_index("ix_briefs_tenant_id", table_name="briefs")
    op.drop_table("briefs")
