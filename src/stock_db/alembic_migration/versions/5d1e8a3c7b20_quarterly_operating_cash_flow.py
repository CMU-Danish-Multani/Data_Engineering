"""Store operating cash flow and serve quarterly free cash flow.

Add only: the existing twelve columns of final.company_financials_quarterly
keep their order and meaning; two columns are appended.
"""

from alembic import op


revision = "5d1e8a3c7b20"
down_revision = "9eb117ff2a64"
branch_labels = None
depends_on = None

BASE_COLUMNS = """
    r.ticker, r.fiscal_year, r.fiscal_quarter, r.period_start, r.period_end,
    r.revenue_usd, r.revenue_growth_yoy_pct, c.capex_usd, c.capex_growth_yoy_pct,
    c.capex_pct_of_revenue, i.operating_income_usd,
    100.0 * i.operating_income_usd / nullif(r.revenue_usd, 0) AS operating_margin_pct"""

BASE_JOINS = """
    FROM final.financial_metrics_quarterly r
    LEFT JOIN final.capital_expenditure_quarterly c USING (ticker, period_start, period_end)
    LEFT JOIN dev.quarterly_operating_income i USING (ticker, period_start, period_end)"""


def upgrade():
    op.execute("""
        CREATE TABLE dev.quarterly_operating_cash_flow (
            ticker text NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            operating_cash_flow_usd bigint NOT NULL,
            source_facts jsonb NOT NULL,
            PRIMARY KEY (ticker, period_start, period_end),
            FOREIGN KEY (ticker, period_start, period_end)
                REFERENCES dev.quarterly_revenue (ticker, period_start, period_end)
        )
    """)
    op.execute(f"""
        CREATE OR REPLACE VIEW final.company_financials_quarterly AS
        SELECT {BASE_COLUMNS},
               o.operating_cash_flow_usd,
               o.operating_cash_flow_usd - c.capex_usd AS free_cash_flow_usd
        {BASE_JOINS}
        LEFT JOIN dev.quarterly_operating_cash_flow o USING (ticker, period_start, period_end)
    """)


def downgrade():
    # CREATE OR REPLACE cannot drop columns, so the view is rebuilt as in 9eb117ff2a64.
    op.execute("DROP VIEW final.company_financials_quarterly")
    op.execute(f"CREATE VIEW final.company_financials_quarterly AS SELECT {BASE_COLUMNS} {BASE_JOINS}")
    op.execute("DROP TABLE dev.quarterly_operating_cash_flow")
