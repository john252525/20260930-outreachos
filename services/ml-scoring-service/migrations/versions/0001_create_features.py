"""create contact_features

Revision ID: 0001_create_features
Revises:
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_features"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_features",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role_category", sa.String(32), nullable=True),
        sa.Column("seniority", sa.String(32), nullable=True),
        sa.Column("company_industry", sa.String(255), nullable=True),
        sa.Column("company_size_range", sa.String(16), nullable=True),
        sa.Column("company_country", sa.String(2), nullable=True),
        sa.Column("company_employee_count", sa.Integer, nullable=True),
        sa.Column("company_signals_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("days_since_company_created", sa.Integer, nullable=True),
        sa.Column("has_reply", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("has_positive_reply", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("messages_sent", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_message_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_contact_features_tenant_contact",
        "contact_features",
        ["tenant_id", "contact_id"],
        unique=True,
    )
    op.execute("ALTER TABLE contact_features ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE contact_features FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY contact_features_tenant_isolation ON contact_features
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS contact_features_tenant_isolation ON contact_features")
    op.drop_table("contact_features")
