"""add cache token columns and is_peak to llm_calls

Revision ID: 0002_llm_call_tokens
Revises: 0001_create_llm_calls
Create Date: 2026-09-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_llm_call_tokens"
down_revision = "0001_create_llm_calls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_calls",
        sa.Column("tokens_in_cache_hit", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "llm_calls",
        sa.Column("tokens_in_cache_miss", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "llm_calls",
        sa.Column("is_peak", sa.Boolean, nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("llm_calls", "is_peak")
    op.drop_column("llm_calls", "tokens_in_cache_miss")
    op.drop_column("llm_calls", "tokens_in_cache_hit")
