"""create flows and flow_steps

Revision ID: 0001_create_flows
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_flows"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("flow_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("brief_id", sa.String(36), nullable=True),
        sa.Column("icp_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("search_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("current_step", sa.String(64), nullable=True),
        sa.Column("progress", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("total_steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed_steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_steps", sa.Integer, nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_flows_tenant_type_status", "flows", ["tenant_id", "flow_type", "status"])
    op.create_index("ix_flows_tenant_brief", "flows", ["tenant_id", "brief_id"])
    op.create_index("ix_flows_tenant_status", "flows", ["tenant_id", "status"])
    op.create_index("ix_flows_tenant_icp", "flows", ["tenant_id", "icp_id"])
    op.create_index("ix_flows_tenant_search_job", "flows", ["tenant_id", "search_job_id"])

    op.execute("ALTER TABLE flows ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE flows FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY flows_tenant_isolation ON flows
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)

    op.create_table(
        "flow_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "flow_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("flows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("input_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("output_data", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_flow_steps_flow_step", "flow_steps", ["flow_id", "step_name"])
    op.create_index("ix_flow_steps_status_retry", "flow_steps", ["status", "next_retry_at"])
    op.create_index("ix_flow_steps_tenant_flow", "flow_steps", ["tenant_id", "flow_id"])

    op.execute("ALTER TABLE flow_steps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE flow_steps FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY flow_steps_tenant_isolation ON flow_steps
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS flow_steps_tenant_isolation ON flow_steps")
    op.drop_table("flow_steps")
    op.execute("DROP POLICY IF EXISTS flows_tenant_isolation ON flows")
    op.drop_table("flows")
