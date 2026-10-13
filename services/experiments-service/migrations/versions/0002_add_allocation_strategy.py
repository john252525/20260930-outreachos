"""add allocation_strategy to experiments

Revision ID: 0002_add_allocation_strategy
Revises: 0001_create_experiments
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_add_allocation_strategy"
down_revision = "0001_create_experiments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "experiments",
        sa.Column("allocation_strategy", sa.String(32), nullable=False, server_default="fixed"),
    )


def downgrade() -> None:
    op.drop_column("experiments", "allocation_strategy")
