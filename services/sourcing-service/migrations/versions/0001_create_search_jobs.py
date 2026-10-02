"""create search_jobs and search_job_items

Revision ID: 0001_create_search_jobs
Revises:
Create Date: 2026-10-01
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_search_jobs"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("icp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("segment_id", sa.String(36), nullable=False),
        sa.Column("brief_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("progress", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("candidates_raw_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("candidates_normalized_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("candidates_persisted_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("companies_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("companies_merged", sa.Integer, nullable=False, server_default="0"),
        sa.Column("contacts_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("contacts_merged", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("error_stage", sa.String(32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_search_jobs_tenant_status", "search_jobs", ["tenant_id", "status"])
    op.create_index("ix_search_jobs_tenant_icp", "search_jobs", ["tenant_id", "icp_id"])
    op.create_index("ix_search_jobs_tenant_created", "search_jobs", ["tenant_id", "created_at"])

    op.create_table(
        "search_job_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "job_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("search_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_url", sa.Text, nullable=True),
        sa.Column("raw_payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("normalized_company", postgresql.JSONB, nullable=True),
        sa.Column("normalized_contacts", postgresql.JSONB, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("score_breakdown", postgresql.JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="raw"),
        sa.Column("skip_reason", sa.String(128), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("contact_ids", postgresql.JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_search_job_items_job", "search_job_items", ["job_id"])
    op.create_index(
        "ix_search_job_items_tenant_status", "search_job_items", ["tenant_id", "status"]
    )
    op.create_index("ix_search_job_items_score", "search_job_items", ["tenant_id", "score"])

    for table in ["search_jobs", "search_job_items"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """)


def downgrade() -> None:
    for table in ["search_jobs", "search_job_items"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("search_job_items")
    op.drop_table("search_jobs")
