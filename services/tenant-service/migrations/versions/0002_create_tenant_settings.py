"""create tenant_settings

Revision ID: 0002_create_tenant_settings
Revises: 0001_create_tenants
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_create_tenant_settings"
down_revision = "0001_create_tenants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("auto_brief_to_icp", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("auto_icp_to_sourcing", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("auto_contacts_to_drafts", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("auto_drafts_to_review", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("auto_approved_to_send", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("auto_revision_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("default_sources", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("default_limit_per_source", sa.Integer, nullable=False, server_default="50"),
        sa.Column("max_sources_per_search", sa.Integer, nullable=False, server_default="5"),
        sa.Column("default_channel", sa.String(16), nullable=False, server_default="email"),
        sa.Column(
            "default_max_contacts_per_flow", sa.Integer, nullable=False, server_default="100"
        ),
        sa.Column("default_sender_daily_limit", sa.Integer, nullable=False, server_default="30"),
        sa.Column("email_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("telegram_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("linkedin_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("whatsapp_enabled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("alert_reply_rate_threshold", sa.Float, nullable=False, server_default="0.02"),
        sa.Column("alert_bounce_rate_threshold", sa.Float, nullable=False, server_default="0.05"),
        sa.Column("quota_llm_tokens_month", sa.Integer, nullable=True),
        sa.Column("quota_messages_day", sa.Integer, nullable=True),
        sa.Column("quota_contacts_max", sa.Integer, nullable=True),
        sa.Column("branding", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("uq_tenant_settings_tenant", "tenant_settings", ["tenant_id"], unique=True)

    op.execute("ALTER TABLE tenant_settings ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE tenant_settings FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_settings_tenant_isolation ON tenant_settings
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_settings_tenant_isolation ON tenant_settings")
    op.drop_table("tenant_settings")
