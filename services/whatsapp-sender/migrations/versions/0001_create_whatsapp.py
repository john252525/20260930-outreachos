"""create whatsapp_accounts, whatsapp_templates, whatsapp_send_attempts

Revision ID: 0001_create_whatsapp
Revises:
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_whatsapp"
down_revision = None
branch_labels = None
depends_on = None


def _rls(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {table}_tenant_isolation ON {table}
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def upgrade() -> None:
    op.create_table(
        "whatsapp_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("phone_number", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("provider_account_id", sa.String(128), nullable=False),
        sa.Column("api_key_encrypted", sa.Text, nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="unverified"),
        sa.Column("daily_sent_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("daily_limit_current", sa.Integer, nullable=False, server_default="100"),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_whatsapp_accounts_phone", "whatsapp_accounts", ["tenant_id", "phone_number"]
    )
    op.create_index(
        "ix_whatsapp_accounts_tenant_status", "whatsapp_accounts", ["tenant_id", "status"]
    )
    _rls("whatsapp_accounts")

    op.create_table(
        "whatsapp_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("language", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("variables_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("provider_template_id", sa.String(128), nullable=False, server_default=""),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_whatsapp_templates", "whatsapp_templates", ["tenant_id", "name", "language"]
    )
    _rls("whatsapp_templates")

    op.create_table(
        "whatsapp_send_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("whatsapp_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("to_phone", sa.String(20), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=True),
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
        "ix_whatsapp_attempts_tenant_message", "whatsapp_send_attempts", ["tenant_id", "message_id"]
    )
    op.create_index(
        "ix_whatsapp_attempts_tenant_status", "whatsapp_send_attempts", ["tenant_id", "status"]
    )
    _rls("whatsapp_send_attempts")


def downgrade() -> None:
    for table in ("whatsapp_send_attempts", "whatsapp_templates", "whatsapp_accounts"):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.drop_table(table)
