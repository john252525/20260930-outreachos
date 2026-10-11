"""create replies table

Revision ID: 0001_create_replies
Revises:
Create Date: 2026-10-11
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_replies"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_email", sa.String(320), nullable=False),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("raw_content", sa.Text, nullable=False),
        sa.Column("language", sa.String(8), nullable=True),
        sa.Column("in_reply_to", sa.String(255), nullable=True),
        sa.Column("references", sa.Text, nullable=True),
        sa.Column("message_id_header", sa.String(255), nullable=True),
        sa.Column("classification", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("category", sa.String(32), nullable=True),
        sa.Column("classification_confidence", sa.Float, nullable=True),
        sa.Column("suggested_next_action", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("handled_by", sa.String(128), nullable=True),
        sa.Column("handled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_replies_tenant_message", "replies", ["tenant_id", "message_id"])
    op.create_index("ix_replies_tenant_contact", "replies", ["tenant_id", "contact_id"])
    op.create_index("ix_replies_tenant_status", "replies", ["tenant_id", "status"])
    op.create_index("ix_replies_tenant_received", "replies", ["tenant_id", "received_at"])
    op.create_index("ix_replies_tenant_category", "replies", ["tenant_id", "category"])
    op.create_index(
        "ix_replies_tenant_category_conf",
        "replies",
        ["tenant_id", "category", "classification_confidence"],
    )
    op.create_index(
        "uq_replies_tenant_message_from",
        "replies",
        ["tenant_id", "message_id", "from_email"],
        unique=True,
    )

    op.execute("ALTER TABLE replies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE replies FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY replies_tenant_isolation ON replies
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS replies_tenant_isolation ON replies")
    op.drop_table("replies")
