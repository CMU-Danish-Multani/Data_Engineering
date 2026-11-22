"""Create and seed the five companies tracked by the dashboard."""

from alembic import op
import sqlalchemy as sa


revision = "832f401bb5ae"
down_revision = "596cdf2cfdf4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    companies = op.create_table(
        "companies",
        sa.Column("ticker", sa.Text(), primary_key=True),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("cik", sa.String(10), nullable=False, unique=True),
        sa.Column("fiscal_year_end_month", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("cik ~ '^[0-9]{10}$'", name="ck_companies_cik_format"),
        sa.CheckConstraint(
            "fiscal_year_end_month BETWEEN 1 AND 12",
            name="ck_companies_fiscal_year_end_month",
        ),
        schema="public",
    )

    # Project architecture, page 20. GOOGL represents Alphabet at the company level.
    company_rows = [
        ("MSFT", "Microsoft", "0000789019", 6),
        ("GOOGL", "Alphabet", "0001652044", 12),
        ("AMZN", "Amazon", "0001018724", 12),
        ("META", "Meta", "0001326801", 12),
        ("NVDA", "NVIDIA", "0001045810", 1),
    ]
    op.bulk_insert(
        companies,
        [
            dict(ticker=ticker, company_name=name, cik=cik, fiscal_year_end_month=month)
            for ticker, name, cik, month in company_rows
        ],
    )


def downgrade() -> None:
    op.drop_table("companies", schema="public")
