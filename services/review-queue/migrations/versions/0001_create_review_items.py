"""create review_items table

Revision ID: 0001_create_review_items
Revises:
Create Date: 2026-10-02
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_review_items"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("assigned_to", sa.String(128), nullable=True),
        sa.Column("reviewed_by", sa.String(128), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("snapshot", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("edit", postgresql.JSONB, nullable=True),
        sa.Column("rejection", postgresql.JSONB, nullable=True),
        sa.Column("scheduled_send_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_review_items_tenant_status", "review_items", ["tenant_id", "status"])
    op.create_index(
        "ix_review_items_tenant_priority_status",
        "review_items",
        ["tenant_id", "priority", "status"],
    )
    op.create_index("ix_review_items_tenant_assigned", "review_items", ["tenant_id", "assigned_to"])
    op.create_index("ix_review_items_created", "review_items", ["tenant_id", "created_at"])
    op.create_index(
        "ix_review_items_message", "review_items", ["tenant_id", "message_id"], unique=True
    )

    op.execute("ALTER TABLE review_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE review_items FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY review_items_tenant_isolation ON review_items
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS review_items_tenant_isolation ON review_items")
    op.drop_table("review_items")
