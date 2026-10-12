"""create telegram_accounts and telegram_send_attempts

Revision ID: 0001_create_telegram
Revises:
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_telegram"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", sa.String(16), nullable=False),
        sa.Column("bot_token_encrypted", sa.Text, nullable=True),
        sa.Column("bot_username", sa.String(64), nullable=True),
        sa.Column("api_id", sa.Integer, nullable=True),
        sa.Column("api_hash_encrypted", sa.Text, nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("session_string_encrypted", sa.Text, nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("daily_sent_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_limit_current", sa.Integer, nullable=False, server_default="3"),
        sa.Column("hourly_limit_current", sa.Integer, nullable=False, server_default="1"),
        sa.Column("warmup_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flood_wait_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_telegram_accounts_phone", "telegram_accounts", ["tenant_id", "phone"]
    )
    op.create_unique_constraint(
        "uq_telegram_accounts_bot", "telegram_accounts", ["tenant_id", "bot_username"]
    )
    op.create_index(
        "ix_telegram_accounts_tenant_status", "telegram_accounts", ["tenant_id", "status"]
    )

    op.execute("ALTER TABLE telegram_accounts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE telegram_accounts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY telegram_accounts_tenant_isolation ON telegram_accounts
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)

    op.create_table(
        "telegram_send_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telegram_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("to_handle", sa.String(128), nullable=False),
        sa.Column("to_chat_id", sa.String(64), nullable=True),
        sa.Column("telegram_message_id", sa.String(64), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("flood_wait_seconds", sa.Integer, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_telegram_attempts_tenant_message",
        "telegram_send_attempts",
        ["tenant_id", "message_id"],
    )
    op.create_index(
        "ix_telegram_attempts_tenant_status", "telegram_send_attempts", ["tenant_id", "status"]
    )

    op.execute("ALTER TABLE telegram_send_attempts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE telegram_send_attempts FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY telegram_attempts_tenant_isolation ON telegram_send_attempts
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS telegram_attempts_tenant_isolation ON telegram_send_attempts")
    op.drop_table("telegram_send_attempts")
    op.execute("DROP POLICY IF EXISTS telegram_accounts_tenant_isolation ON telegram_accounts")
    op.drop_table("telegram_accounts")
