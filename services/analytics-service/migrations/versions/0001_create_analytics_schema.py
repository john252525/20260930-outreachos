"""create analytics schema and materialized views

Revision ID: 0001_create_analytics_schema
Revises:
Create Date: 2026-10-11
"""

from alembic import op

revision = "0001_create_analytics_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS analytics")
    op.execute("GRANT USAGE ON SCHEMA analytics TO outreach_app")
    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO outreach_app")

    # --- MV: daily message metrics by tenant x day x channel x template ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_message_metrics AS
        SELECT
            m.tenant_id,
            DATE(m.created_at) AS day,
            m.channel,
            m.personalization->>'template_id' AS template_id,
            m.personalization->>'template_version' AS template_version,
            COUNT(*) FILTER (WHERE m.status IN ('sent', 'delivered', 'replied', 'closed')) AS sent_count,
            COUNT(*) FILTER (WHERE m.status = 'bounced') AS bounced_count,
            COUNT(*) FILTER (WHERE m.status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE m.status = 'replied') AS replied_count,
            COUNT(*) FILTER (WHERE m.status = 'approved') AS approved_count,
            COUNT(*) FILTER (WHERE m.status = 'draft') AS draft_count,
            COUNT(*) FILTER (WHERE m.status = 'rejected') AS rejected_count,
            AVG(m.word_count) AS avg_word_count
        FROM messages m
        GROUP BY 1, 2, 3, 4, 5
    """)
    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_message_metrics_pk
        ON analytics.mv_daily_message_metrics
        (tenant_id, day, channel, COALESCE(template_id, ''), COALESCE(template_version, ''))
    """)

    # --- MV: daily reply metrics ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_reply_metrics AS
        SELECT
            r.tenant_id,
            DATE(r.received_at) AS day,
            r.category,
            r.channel,
            COUNT(*) AS reply_count,
            AVG(r.classification_confidence) AS avg_confidence,
            COUNT(DISTINCT r.contact_id) AS unique_contacts,
            COUNT(DISTINCT r.message_id) AS unique_messages
        FROM replies r
        WHERE r.status IN ('classified', 'handled', 'needs_review')
        GROUP BY 1, 2, 3, 4
    """)
    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_reply_metrics_pk
        ON analytics.mv_daily_reply_metrics
        (tenant_id, day, COALESCE(category, ''), channel)
    """)

    # --- MV: daily sender metrics ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_sender_metrics AS
        SELECT
            sa.tenant_id,
            DATE(sat.sent_at) AS day,
            sa.id AS sender_account_id,
            sa.email AS sender_email,
            COUNT(*) FILTER (WHERE sat.status = 'sent') AS sent_count,
            COUNT(*) FILTER (WHERE sat.status = 'failed') AS failed_count,
            COUNT(*) FILTER (WHERE sat.status = 'bounced') AS bounced_count
        FROM send_attempts sat
        JOIN sender_accounts sa ON sa.id = sat.sender_account_id
        WHERE sat.sent_at IS NOT NULL
        GROUP BY 1, 2, 3, 4
    """)
    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_sender_metrics_pk
        ON analytics.mv_daily_sender_metrics (tenant_id, day, sender_account_id)
    """)

    # --- MV: sourcing funnel ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_daily_sourcing_metrics AS
        SELECT
            sj.tenant_id,
            DATE(sj.created_at) AS day,
            sj.icp_id,
            COUNT(*) AS jobs_count,
            SUM(sj.candidates_raw_count) AS raw_count,
            SUM(sj.candidates_normalized_count) AS normalized_count,
            SUM(sj.candidates_persisted_count) AS persisted_count,
            SUM(sj.companies_created) AS companies_created,
            SUM(sj.contacts_created) AS contacts_created,
            SUM(sj.total_cost_usd) AS total_cost_usd,
            AVG(sj.duration_ms) AS avg_duration_ms
        FROM search_jobs sj
        WHERE sj.status = 'completed'
        GROUP BY 1, 2, 3
    """)
    op.execute("""
        CREATE UNIQUE INDEX ix_mv_daily_sourcing_metrics_pk
        ON analytics.mv_daily_sourcing_metrics (tenant_id, day, icp_id)
    """)

    # --- MV: overall funnel per tenant ---
    op.execute("""
        CREATE MATERIALIZED VIEW analytics.mv_funnel AS
        SELECT
            m.tenant_id,
            COUNT(DISTINCT m.contact_id) AS contacted,
            COUNT(DISTINCT m.contact_id) FILTER (
                WHERE m.status IN ('sent', 'delivered', 'replied', 'closed')
            ) AS sent,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'replied') AS replied,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'bounced') AS bounced,
            COUNT(DISTINCT m.contact_id) FILTER (WHERE m.status = 'closed') AS closed,
            COUNT(*) FILTER (WHERE m.status = 'approved') AS approved,
            COUNT(*) FILTER (WHERE m.status = 'draft') AS draft
        FROM messages m
        GROUP BY 1
    """)
    op.execute("CREATE UNIQUE INDEX ix_mv_funnel_pk ON analytics.mv_funnel (tenant_id)")

    op.execute("GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO outreach_app")


def downgrade() -> None:
    for mv in [
        "mv_funnel",
        "mv_daily_sourcing_metrics",
        "mv_daily_sender_metrics",
        "mv_daily_reply_metrics",
        "mv_daily_message_metrics",
    ]:
        op.execute(f"DROP MATERIALIZED VIEW IF EXISTS analytics.{mv}")
    op.execute("DROP SCHEMA IF EXISTS analytics CASCADE")
