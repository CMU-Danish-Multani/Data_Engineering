"""Store product KPIs read from earnings releases and serve them with growth and margins.

Growth uses the prior-year column of the same release where it exists, else
the value four quarters earlier with the same definition note. Ratios are
derived in SQL from stored inputs of the same quarter.
"""

from alembic import op


revision = "9c4b2f61e8a7"
down_revision = "7a2c4e9b1d36"
branch_labels = None
depends_on = None


def ratio(name, numerator, denominator_sql, note):
    return f"""
        SELECT n.ticker, n.fiscal_year, n.fiscal_quarter, n.period_start, n.period_end,
               '{name}'::text AS kpi, 100.0 * n.value / nullif({denominator_sql}, 0) AS value, 'pct'::text AS unit,
               NULL::numeric AS yoy_growth_pct, n.source_url, '{note}'::text AS definition_note
        FROM k n
        LEFT JOIN k d ON (d.ticker, d.period_start, d.period_end) = (n.ticker, n.period_start, n.period_end)
                     AND d.kpi = '{numerator.replace("operating_income", "revenue")}'
        WHERE n.kpi = '{numerator}'"""


def upgrade():
    op.execute("""
        CREATE TABLE dev.quarterly_product_kpis (
            ticker text NOT NULL,
            period_start date NOT NULL,
            period_end date NOT NULL,
            kpi text NOT NULL,
            value numeric,
            unit text NOT NULL CHECK (unit IN ('USD', 'pct')),
            source_url text NOT NULL,
            accession text NOT NULL,
            source_text text,
            method text,
            definition_note text,
            PRIMARY KEY (ticker, period_start, period_end, kpi),
            FOREIGN KEY (ticker, period_start, period_end)
                REFERENCES dev.quarterly_revenue (ticker, period_start, period_end),
            CHECK (value IS NOT NULL OR definition_note IS NOT NULL),
            CHECK (value IS NULL OR source_text IS NOT NULL)
        )
    """)
    op.execute(f"""
        CREATE VIEW final.product_kpis_quarterly AS
        WITH k AS (
            SELECT p.*, f.fiscal_year, f.fiscal_quarter, f.revenue_usd AS company_revenue_usd
            FROM dev.quarterly_product_kpis p
            JOIN final.financial_metrics_quarterly f USING (ticker, period_start, period_end)
        ), reported AS (
            SELECT k.*, lag(value, 4) OVER w AS value_year_ago, lag(definition_note, 4) OVER w AS note_year_ago,
                   lag(period_end, 4) OVER w AS end_year_ago
            FROM k WHERE kpi NOT LIKE '%prior_year%'
            WINDOW w AS (PARTITION BY ticker, kpi ORDER BY period_end)
        )
        SELECT r.ticker, r.fiscal_year, r.fiscal_quarter, r.period_start, r.period_end, r.kpi, r.value, r.unit,
               CASE WHEN r.unit <> 'USD' THEN NULL
                    WHEN py.value IS NOT NULL THEN 100.0 * (r.value - py.value) / nullif(py.value, 0)
                    WHEN r.note_year_ago IS NOT DISTINCT FROM r.definition_note
                         AND r.period_end - r.end_year_ago BETWEEN 350 AND 378
                    THEN 100.0 * (r.value - r.value_year_ago) / nullif(r.value_year_ago, 0)
               END AS yoy_growth_pct,
               r.source_url, r.definition_note
        FROM reported r
        LEFT JOIN dev.quarterly_product_kpis py
               ON (py.ticker, py.period_start, py.period_end) = (r.ticker, r.period_start, r.period_end)
              AND r.kpi LIKE '%\\_revenue\\_usd'
              AND py.kpi = replace(r.kpi, '_revenue_usd', '_revenue_prior_year_usd')
        UNION ALL {ratio("aws_operating_margin_pct", "aws_operating_income_usd", "d.value",
                         "Derived: AWS segment operating income / AWS segment sales.")}
        UNION ALL {ratio("google_cloud_operating_margin_pct", "google_cloud_operating_income_usd", "d.value",
                         "Derived: Google Cloud operating income / Google Cloud revenue.")}
        UNION ALL {ratio("data_center_share_of_revenue_pct", "data_center_revenue_usd", "n.company_revenue_usd",
                         "Derived: Data Center revenue / total company revenue.")}
    """)


def downgrade():
    op.execute("DROP VIEW final.product_kpis_quarterly")
    op.execute("DROP TABLE dev.quarterly_product_kpis")
