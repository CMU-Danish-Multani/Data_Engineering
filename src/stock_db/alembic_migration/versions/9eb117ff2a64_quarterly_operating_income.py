"""Store operating income and serve company-level financial metrics by quarter."""

from alembic import op


revision = "9eb117ff2a64"
down_revision = "cf9ac120e765"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE dev.quarterly_operating_income (
            ticker text NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            operating_income_usd bigint NOT NULL,
            source_facts jsonb NOT NULL,
            PRIMARY KEY (ticker, period_start, period_end),
            FOREIGN KEY (ticker, period_start, period_end)
                REFERENCES dev.quarterly_revenue (ticker, period_start, period_end)
        )
    """)
    op.execute("""
        CREATE VIEW final.company_financials_quarterly AS
        SELECT r.ticker, r.fiscal_year, r.fiscal_quarter, r.period_start, r.period_end,
               r.revenue_usd, r.revenue_growth_yoy_pct, c.capex_usd, c.capex_growth_yoy_pct,
               c.capex_pct_of_revenue, i.operating_income_usd,
               100.0 * i.operating_income_usd / nullif(r.revenue_usd, 0) AS operating_margin_pct
        FROM final.financial_metrics_quarterly r
        LEFT JOIN final.capital_expenditure_quarterly c USING (ticker, period_start, period_end)
        LEFT JOIN dev.quarterly_operating_income i USING (ticker, period_start, period_end)
    """)


def downgrade():
    op.execute("DROP VIEW final.company_financials_quarterly")
    op.execute("DROP TABLE dev.quarterly_operating_income")
