"""Compare revenue for the same fiscal quarter across consecutive years."""

from alembic import op


revision = "34f7b1a0c952"
down_revision = "2c9674fb86a1"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE SCHEMA IF NOT EXISTS final")
    op.execute("""
        CREATE VIEW final.financial_metrics_quarterly AS
        WITH fiscal_years AS (
            -- The Q4 row retains the annual filing's actual start and end dates.
            SELECT ticker, (source_facts #>> '{inputs,annual,start}')::date AS year_start,
                   period_end AS year_end
            FROM dev.quarterly_revenue
            WHERE (source_facts #>> '{inputs,annual,end}')::date = period_end
        ), numbered AS (
            SELECT r.ticker, y.year_start, y.year_end, r.period_start, r.period_end,
                   r.revenue_usd, r.filing_id,
                   row_number() OVER quarter_order AS fiscal_quarter,
                   lag(r.period_end) OVER quarter_order AS previous_end
            FROM fiscal_years y
            JOIN dev.quarterly_revenue r ON r.ticker = y.ticker
                 AND r.period_start >= y.year_start AND r.period_end <= y.year_end
            WINDOW quarter_order AS (
                PARTITION BY r.ticker, y.year_end ORDER BY r.period_start, r.period_end
            )
        ), complete_years AS (
            SELECT ticker, year_end
            FROM numbered
            GROUP BY ticker, year_end
            HAVING count(*) = 4
               AND bool_and(period_start = coalesce(previous_end + 1, year_start))
               AND bool_and(period_end >= period_start)
               AND max(period_end) = year_end
        ), quarters AS (
            SELECT n.*, extract(year FROM year_end)::integer AS fiscal_year
            FROM numbered n JOIN complete_years USING (ticker, year_end)
        )
        SELECT q.ticker, q.fiscal_year, q.fiscal_quarter, q.period_start, q.period_end,
               q.revenue_usd, p.period_end AS prior_year_period_end,
               p.revenue_usd AS prior_year_revenue_usd,
               100.0 * (q.revenue_usd - p.revenue_usd) / nullif(p.revenue_usd, 0)
                   AS revenue_growth_yoy_pct,
               q.filing_id, p.filing_id AS prior_year_filing_id
        FROM quarters q LEFT JOIN quarters p
          ON p.ticker = q.ticker AND p.fiscal_year = q.fiscal_year - 1
         AND p.fiscal_quarter = q.fiscal_quarter
    """)


def downgrade():
    op.execute("DROP VIEW final.financial_metrics_quarterly")
