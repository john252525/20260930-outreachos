"""create linkedin_accounts and linkedin_send_attempts

Revision ID: 0001_create_linkedin
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_linkedin"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "linkedin_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_encrypted", sa.Text, nullable=False),
        sa.Column("cookies_encrypted", sa.Text, nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("proxy_url", sa.String(512), nullable=True),
        sa.Column("proxy_type", sa.String(16), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("daily_sent_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_limit_current", sa.Integer, nullable=False, server_default="5"),
        sa.Column("weekly_limit_current", sa.Integer, nullable=False, server_default="20"),
        sa.Column("warmup_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("ban_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_linkedin_accounts_tenant_email", "linkedin_accounts", ["tenant_id", "email"]
    )
    op.create_index(
        "ix_linkedin_accounts_tenant_status", "linkedin_accounts", ["tenant_id", "status"]
    )

    op.execute("ALTER TABLE linkedin_accounts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE linkedin_accounts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY linkedin_accounts_tenant_isolation ON linkedin_accounts
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)

    op.create_table(
        "linkedin_send_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("linkedin_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("to_handle", sa.String(256), nullable=False),
        sa.Column("provider_message_id", sa.String(128), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_linkedin_attempts_tenant_message", "linkedin_send_attempts", ["tenant_id", "message_id"]
    )
    op.create_index(
        "ix_linkedin_attempts_tenant_status", "linkedin_send_attempts", ["tenant_id", "status"]
    )

    op.execute("ALTER TABLE linkedin_send_attempts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE linkedin_send_attempts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY linkedin_attempts_tenant_isolation ON linkedin_send_attempts
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS linkedin_attempts_tenant_isolation ON linkedin_send_attempts")
    op.drop_table("linkedin_send_attempts")
    op.execute("DROP POLICY IF EXISTS linkedin_accounts_tenant_isolation ON linkedin_accounts")
    op.drop_table("linkedin_accounts")
