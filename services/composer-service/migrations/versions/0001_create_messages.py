"""create messages table

Revision ID: 0001_create_messages
Revises:
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_messages"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("sequence_step", sa.Integer, nullable=False, server_default="1"),
        sa.Column("sequence_total_steps", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "parent_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_followup", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("followup_after_days", sa.Integer, nullable=True),
        sa.Column("subject", sa.String(255), nullable=True),
        sa.Column("body_text", sa.Text, nullable=False, server_default=""),
        sa.Column("body_html", sa.Text, nullable=True),
        sa.Column("language", sa.String(8), nullable=False, server_default="ru"),
        sa.Column("word_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("personalization", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("sender", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("recipient_snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("experiment", postgresql.JSONB, nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivery", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("engagement", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("review", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_messages_tenant_status", "messages", ["tenant_id", "status"])
    op.create_index("ix_messages_tenant_contact", "messages", ["tenant_id", "contact_id"])
    op.create_index("ix_messages_tenant_company", "messages", ["tenant_id", "company_id"])
    op.create_index("ix_messages_tenant_channel", "messages", ["tenant_id", "channel"])
    op.create_index("ix_messages_tenant_created", "messages", ["tenant_id", "created_at"])
    op.create_index("ix_messages_scheduled", "messages", ["tenant_id", "scheduled_at"])
    op.create_index("ix_messages_sent", "messages", ["tenant_id", "sent_at"])
    op.execute(
        "CREATE INDEX ix_messages_personalization_gin ON messages USING gin (personalization jsonb_path_ops)"
    )

    op.execute("ALTER TABLE messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE messages FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY messages_tenant_isolation ON messages
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS messages_tenant_isolation ON messages")
    op.drop_table("messages")
