"""create companies, contacts, emails, phones, stoplist

Revision ID: 0001_create_companies_contacts
Revises:
Create Date: 2026-09-30
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_create_companies_contacts"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("name_normalized", sa.String(512), nullable=False),
        sa.Column("domain_normalized", sa.String(255), nullable=True),
        sa.Column("inn", sa.String(12), nullable=True),
        sa.Column("ogrn", sa.String(15), nullable=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("contacts_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_companies_tenant_fingerprint", "companies", ["tenant_id", "fingerprint"], unique=True
    )
    op.create_index("ix_companies_tenant_status", "companies", ["tenant_id", "status"])
    op.create_index("ix_companies_tenant_created", "companies", ["tenant_id", "created_at"])
    op.create_index("ix_companies_name_norm", "companies", ["name_normalized"])
    op.create_index("ix_companies_domain_norm", "companies", ["domain_normalized"])
    op.create_index("ix_companies_inn", "companies", ["inn"])
    op.create_index("ix_companies_ogrn", "companies", ["ogrn"])
    op.execute(
        "CREATE INDEX ix_companies_payload_gin ON companies USING gin (payload jsonb_path_ops)"
    )

    # --- contacts ---
    op.create_table(
        "contacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="candidate"),
        sa.Column("full_name_normalized", sa.String(512), nullable=False),
        sa.Column("primary_email", sa.String(320), nullable=True),
        sa.Column("primary_phone", sa.String(20), nullable=True),
        sa.Column("role_category", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("seniority", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replied_positive", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="1.0"),
        sa.Column("metadata", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_contacts_tenant_fingerprint", "contacts", ["tenant_id", "fingerprint"], unique=True
    )
    op.create_index("ix_contacts_tenant_status", "contacts", ["tenant_id", "status"])
    op.create_index("ix_contacts_tenant_created", "contacts", ["tenant_id", "created_at"])
    op.create_index("ix_contacts_company", "contacts", ["company_id"])
    op.create_index("ix_contacts_name_norm", "contacts", ["full_name_normalized"])
    op.create_index("ix_contacts_primary_email", "contacts", ["primary_email"])
    op.create_index("ix_contacts_primary_phone", "contacts", ["primary_phone"])
    op.execute(
        "CREATE INDEX ix_contacts_payload_gin ON contacts USING gin (payload jsonb_path_ops)"
    )

    # --- contact_emails ---
    op.create_table(
        "contact_emails",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_contact_emails_tenant_value", "contact_emails", ["tenant_id", "value"], unique=True
    )
    op.create_index("ix_contact_emails_contact", "contact_emails", ["contact_id"])

    # --- contact_phones ---
    op.create_table(
        "contact_phones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "contact_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.String(20), nullable=False),
        sa.Column("type", sa.String(16), nullable=False, server_default="unknown"),
        sa.Column("is_primary", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_whatsapp", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_telegram", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
        sa.Column("evidence", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.create_index(
        "ix_contact_phones_tenant_value", "contact_phones", ["tenant_id", "value"], unique=True
    )
    op.create_index("ix_contact_phones_contact", "contact_phones", ["contact_id"])

    # --- stoplist_entries ---
    op.create_table(
        "stoplist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("reason", sa.String(64), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(128), nullable=False, server_default="system"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_stoplist_lookup", "stoplist_entries", ["kind", "value"])
    op.create_index("ix_stoplist_tenant", "stoplist_entries", ["tenant_id"])
    op.execute("""
        CREATE UNIQUE INDEX uq_stoplist_entry
        ON stoplist_entries (scope, COALESCE(tenant_id, '00000000-0000-0000-0000-000000000000'::uuid), kind, value)
    """)

    # --- RLS ---
    for table, column in [
        ("companies", "tenant_id"),
        ("contacts", "tenant_id"),
        ("contact_emails", "tenant_id"),
        ("contact_phones", "tenant_id"),
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING ({column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
            WITH CHECK ({column} = NULLIF(current_setting('app.tenant_id', true), '')::uuid)
        """)

    op.execute("ALTER TABLE stoplist_entries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stoplist_entries FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY stoplist_entries_isolation ON stoplist_entries
        USING (
            tenant_id IS NULL
            OR tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
        WITH CHECK (
            tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS stoplist_entries_isolation ON stoplist_entries")
    for table in ["contact_phones", "contact_emails", "contacts", "companies"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
    op.drop_table("stoplist_entries")
    op.drop_table("contact_phones")
    op.drop_table("contact_emails")
    op.drop_table("contacts")
    op.drop_table("companies")
