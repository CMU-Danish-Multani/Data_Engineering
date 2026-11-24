"""Store valuation inputs and serve trailing and annual P/E, EV/Revenue and FCF yield.

Prices come from dev.stock_prices_daily (split adjusted), so EPS and shares in
dev.quarterly_valuation_inputs are restated to today's share basis.
"""

from alembic import op


revision = "7a2c4e9b1d36"
down_revision = "5d1e8a3c7b20"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE dev.quarterly_valuation_inputs (
            ticker text NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            diluted_eps_usd numeric NOT NULL,
            eps_method text NOT NULL,
            diluted_shares bigint NOT NULL CHECK (diluted_shares > 0),
            shares_method text NOT NULL,
            total_debt_usd bigint NOT NULL CHECK (total_debt_usd >= 0),
            debt_method text NOT NULL,
            cash_usd bigint NOT NULL CHECK (cash_usd >= 0),
            source_facts jsonb NOT NULL,
            PRIMARY KEY (ticker, period_start, period_end),
            FOREIGN KEY (ticker, period_start, period_end)
                REFERENCES dev.quarterly_revenue (ticker, period_start, period_end)
        )
    """)
    op.execute("""
        CREATE VIEW final.valuation_quarterly AS
        WITH quarters AS (
            SELECT f.ticker, f.fiscal_year, f.fiscal_quarter, f.period_start, f.period_end,
                   v.diluted_shares, v.total_debt_usd, v.debt_method, v.cash_usd,
                   count(*) OVER w4 AS quarters_in_window,
                   f.period_end - first_value(f.period_start) OVER w4 + 1 AS window_days,
                   sum(v.diluted_eps_usd) OVER w4 AS sum_eps,
                   sum(f.revenue_usd) OVER w4 AS sum_revenue,
                   sum(f.free_cash_flow_usd) OVER w4 AS sum_fcf,
                   count(f.free_cash_flow_usd) OVER w4 AS fcf_quarters
            FROM final.company_financials_quarterly f
            JOIN dev.quarterly_valuation_inputs v USING (ticker, period_start, period_end)
            WINDOW w4 AS (PARTITION BY f.ticker ORDER BY f.period_end ROWS BETWEEN 3 PRECEDING AND CURRENT ROW)
        ), year_windows AS (
            SELECT q.*, quarters_in_window = 4 AND window_days BETWEEN 350 AND 378 AS full_year
            FROM quarters q
        ), priced AS (
            SELECT t.*, p.trade_date AS price_date, p.close,
                   CASE WHEN full_year THEN sum_eps END AS ttm_eps,
                   CASE WHEN full_year THEN sum_revenue END AS ttm_revenue_usd,
                   CASE WHEN full_year AND fcf_quarters = 4 THEN sum_fcf END AS ttm_fcf_usd,
                   p.close * t.diluted_shares AS market_cap_usd
            FROM year_windows t
            LEFT JOIN LATERAL (
                SELECT d.trade_date, d.close FROM dev.stock_prices_daily d
                WHERE d.ticker = t.ticker AND d.trade_date <= t.period_end
                  AND d.trade_date > t.period_end - 7
                ORDER BY d.trade_date DESC LIMIT 1
            ) p ON true
        )
        SELECT ticker, fiscal_year, fiscal_quarter, period_start, period_end,
               price_date, close, diluted_shares, market_cap_usd,
               ttm_eps, CASE WHEN ttm_eps > 0 THEN close / ttm_eps END AS pe_ratio,
               total_debt_usd, cash_usd, market_cap_usd + total_debt_usd - cash_usd AS enterprise_value_usd,
               ttm_revenue_usd,
               (market_cap_usd + total_debt_usd - cash_usd) / nullif(ttm_revenue_usd, 0) AS ev_to_revenue,
               ttm_fcf_usd, 100 * ttm_fcf_usd / nullif(market_cap_usd, 0) AS fcf_yield_pct,
               CASE WHEN close IS NULL THEN 'no price within 7 days before period end'
                    WHEN NOT full_year THEN 'fewer than four quarters loaded'
                    WHEN ttm_eps <= 0 THEN 'trailing EPS not positive'
                    ELSE 'ok' END AS valuation_status,
               debt_method
        FROM priced
    """)
    op.execute("""
        CREATE VIEW final.valuation_annual AS
        SELECT * FROM final.valuation_quarterly WHERE fiscal_quarter = 4
    """)
    op.execute("COMMENT ON VIEW final.valuation_annual IS "
               "'Fiscal year valuation: at Q4 the trailing four quarters are the fiscal year.'")


def downgrade():
    op.execute("DROP VIEW final.valuation_annual")
    op.execute("DROP VIEW final.valuation_quarterly")
    op.execute("DROP TABLE dev.quarterly_valuation_inputs")
