"""create sender_accounts and send_attempts

Revision ID: 0001_create_sender_accounts
Revises:
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_sender_accounts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sender_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("smtp_host", sa.String(255), nullable=False),
        sa.Column("smtp_port", sa.Integer, nullable=False, server_default="465"),
        sa.Column("smtp_use_ssl", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("smtp_username", sa.String(320), nullable=False),
        sa.Column("smtp_password_encrypted", sa.Text, nullable=False),
        sa.Column("imap_host", sa.String(255), nullable=False),
        sa.Column("imap_port", sa.Integer, nullable=False, server_default="993"),
        sa.Column("imap_use_ssl", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("imap_username", sa.String(320), nullable=False),
        sa.Column("imap_password_encrypted", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("daily_sent_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_limit_current", sa.Integer, nullable=False, server_default="10"),
        sa.Column("hourly_limit_current", sa.Integer, nullable=False, server_default="5"),
        sa.Column("last_reset_date", sa.Date, nullable=True),
        sa.Column("warmup_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("spf_ok", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dkim_ok", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dmarc_ok", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dns_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_limit_max", sa.Integer, nullable=False, server_default="50"),
        sa.Column("hourly_limit_max", sa.Integer, nullable=False, server_default="10"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "uq_sender_accounts_tenant_email", "sender_accounts", ["tenant_id", "email"], unique=True
    )
    op.create_index("ix_sender_accounts_tenant_status", "sender_accounts", ["tenant_id", "status"])

    op.create_table(
        "send_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sender_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sender_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("to_email", sa.String(320), nullable=False),
        sa.Column("from_email", sa.String(320), nullable=False),
        sa.Column("smtp_response", sa.Text, nullable=True),
        sa.Column("smtp_message_id", sa.String(255), nullable=True),
        sa.Column("bounce_type", sa.String(16), nullable=True),
        sa.Column("bounce_reason", sa.Text, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_send_attempts_tenant_message", "send_attempts", ["tenant_id", "message_id"])
    op.create_index("ix_send_attempts_tenant_status", "send_attempts", ["tenant_id", "status"])
    op.create_index("ix_send_attempts_sent_at", "send_attempts", ["tenant_id", "sent_at"])
    op.create_index("ix_send_attempts_smtp_msg_id", "send_attempts", ["smtp_message_id"])

    for table in ["sender_accounts", "send_attempts"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """)


def downgrade() -> None:
    for table in ["sender_accounts", "send_attempts"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("send_attempts")
    op.drop_table("sender_accounts")
