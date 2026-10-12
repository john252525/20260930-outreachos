"""create template_overrides

Revision ID: 0002_create_template_overrides
Revises: 0001_create_messages
Create Date: 2026-10-12
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002_create_template_overrides"
down_revision = "0001_create_messages"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", sa.String(64), nullable=False),
        sa.Column("base_version", sa.String(16), nullable=False),
        sa.Column("override_version", sa.String(64), nullable=False),
        sa.Column("system_prompt", sa.Text, nullable=False),
        sa.Column("user_prompt_template", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="auto-revision"),
        sa.Column("source_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_unique_constraint(
        "uq_template_override",
        "template_overrides",
        ["tenant_id", "template_id", "override_version"],
    )
    op.create_index(
        "ix_template_overrides_tenant_active",
        "template_overrides",
        ["tenant_id", "template_id", "is_active"],
    )
    op.create_index(
        "ix_template_overrides_tenant_template",
        "template_overrides",
        ["tenant_id", "template_id"],
    )

    op.execute("ALTER TABLE template_overrides ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE template_overrides FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY template_overrides_tenant_isolation ON template_overrides
        USING (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        WITH CHECK (tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS template_overrides_tenant_isolation ON template_overrides")
    op.drop_table("template_overrides")
