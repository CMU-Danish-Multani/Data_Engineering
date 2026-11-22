"""Load one fiscal year of Microsoft quarterly revenue into PostgreSQL."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

from extract_revenue import fiscal_year_argument, quarterly_revenue


def load(fiscal_year):
    load_dotenv(Path(__file__).resolve().parent / "src/stock_db/alembic_migration/.env")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("Set DATABASE_URL to the same PostgreSQL URL used by Alembic.")

    rows = quarterly_revenue(fiscal_year)
    statement = text("""
        INSERT INTO dev.quarterly_revenue AS stored
            (ticker, period_start, period_end, revenue_usd, filing_id, filed_on, source_facts)
        VALUES (:ticker, :period_start, :period_end, :revenue_usd, :filing_id, :filed_on, :source_facts)
        ON CONFLICT (ticker, period_start, period_end) DO UPDATE SET
            revenue_usd = EXCLUDED.revenue_usd,
            filing_id = EXCLUDED.filing_id,
            filed_on = EXCLUDED.filed_on,
            source_facts = EXCLUDED.source_facts
        WHERE EXCLUDED.filed_on >= stored.filed_on
          AND EXCLUDED.source_facts IS DISTINCT FROM stored.source_facts
          AND NOT EXISTS (
              SELECT 1 FROM jsonb_each(stored.source_facts -> 'inputs') AS prior(role, fact)
              WHERE COALESCE(EXCLUDED.source_facts -> 'inputs' -> prior.role ->> 'filed', '')
                    < prior.fact ->> 'filed'
          )
    """).bindparams(bindparam("source_facts", type_=JSONB))
    with create_engine(database_url).begin() as conn:
        conn.execute(statement, rows)
    print(f"Processed {len(rows)} quarters for MSFT FY{fiscal_year}.")


if __name__ == "__main__":
    load(fiscal_year_argument())
