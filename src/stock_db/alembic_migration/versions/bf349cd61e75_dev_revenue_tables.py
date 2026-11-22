"""Move the company reference table to dev and create its quarterly revenue table."""

from alembic import op
import sqlalchemy as sa


revision = "bf349cd61e75"
down_revision = "832f401bb5ae"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.companies SET SCHEMA dev")
    op.create_table(
        "quarterly_revenue",
        sa.Column("ticker", sa.Text(), sa.ForeignKey("dev.companies.ticker"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("revenue_usd", sa.BigInteger(), nullable=False),
        sa.Column("filing_id", sa.Text(), nullable=False),
        sa.Column("filed_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("ticker", "period_start", "period_end"),
        schema="dev",
    )


def downgrade() -> None:
    op.drop_table("quarterly_revenue", schema="dev")
    op.execute("ALTER TABLE dev.companies SET SCHEMA public")
