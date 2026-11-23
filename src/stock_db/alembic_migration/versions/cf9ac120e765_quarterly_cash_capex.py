"""Store quarterly cash CapEx and expose spending, growth and share of revenue."""

from alembic import op


revision = "cf9ac120e765"
down_revision = "34f7b1a0c952"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE dev.quarterly_capex (
            ticker text NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            capex_usd bigint NOT NULL CHECK (capex_usd >= 0),
            source_facts jsonb NOT NULL,
            PRIMARY KEY (ticker, period_start, period_end),
            FOREIGN KEY (ticker, period_start, period_end)
                REFERENCES dev.quarterly_revenue (ticker, period_start, period_end)
        )
    """)
    op.execute("""
        CREATE VIEW final.capital_expenditure_quarterly AS
        SELECT r.ticker, r.fiscal_year, r.fiscal_quarter, r.period_start, r.period_end,
               r.revenue_usd, c.capex_usd, p.capex_usd AS prior_year_capex_usd,
               100.0 * (c.capex_usd - p.capex_usd) / nullif(p.capex_usd, 0)
                   AS capex_growth_yoy_pct,
               100.0 * c.capex_usd / nullif(r.revenue_usd, 0) AS capex_pct_of_revenue
        FROM final.financial_metrics_quarterly r
        LEFT JOIN dev.quarterly_capex c USING (ticker, period_start, period_end)
        LEFT JOIN final.financial_metrics_quarterly prev
            ON (prev.ticker, prev.fiscal_year, prev.fiscal_quarter)
             = (r.ticker, r.fiscal_year - 1, r.fiscal_quarter)
        LEFT JOIN dev.quarterly_capex p
            ON (p.ticker, p.period_start, p.period_end)
             = (prev.ticker, prev.period_start, prev.period_end)
    """)


def downgrade():
    op.execute("DROP VIEW final.capital_expenditure_quarterly")
    op.execute("DROP TABLE dev.quarterly_capex")
