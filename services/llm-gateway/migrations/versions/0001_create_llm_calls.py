"""create llm_calls table

Revision ID: 0001_create_llm_calls
Revises:
Create Date: 2026-09-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_llm_calls"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Numeric(14, 8), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("cached", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("request_body", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("response_text", sa.Text, nullable=False, server_default=""),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("langfuse_trace_id", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_llm_calls_tenant_id", "llm_calls", ["tenant_id"])
    op.create_index("ix_llm_calls_task_type", "llm_calls", ["task_type"])
    op.create_index("ix_llm_calls_prompt_hash", "llm_calls", ["prompt_hash"])
    op.create_index("ix_llm_calls_tenant_created", "llm_calls", ["tenant_id", "created_at"])

    op.execute("ALTER TABLE llm_calls ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE llm_calls FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY llm_calls_tenant_isolation ON llm_calls
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS llm_calls_tenant_isolation ON llm_calls")
    op.drop_index("ix_llm_calls_tenant_created", table_name="llm_calls")
    op.drop_index("ix_llm_calls_prompt_hash", table_name="llm_calls")
    op.drop_index("ix_llm_calls_task_type", table_name="llm_calls")
    op.drop_index("ix_llm_calls_tenant_id", table_name="llm_calls")
    op.drop_table("llm_calls")
