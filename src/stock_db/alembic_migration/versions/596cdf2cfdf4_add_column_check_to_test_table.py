"""Add check column to public.quarterly_revenue.

Revision ID: 596cdf2cfdf4
Revises: 
Create Date: 2026-11-18 23:32:12.199728

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '596cdf2cfdf4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "quarterly_revenue",
        sa.Column("check", sa.Boolean(), nullable=True),
        schema="public",
    )


def downgrade() -> None:
    op.drop_column("quarterly_revenue", "check", schema="public")
