import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from extract_revenue import record


load_dotenv(Path(__file__).resolve().parent / "src/stock_db/alembic_migration/.env")
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise SystemExit("Set DATABASE_URL to the same PostgreSQL URL used by Alembic.")

with create_engine(database_url).begin() as conn:
    conn.execute(
        text("""
            INSERT INTO dev.quarterly_revenue AS current_revenue
                (ticker, period_start, period_end, revenue_usd, filing_id, filed_on)
            VALUES (:ticker, :period_start, :period_end, :revenue_usd, :filing_id, :filed_on)
            ON CONFLICT (ticker, period_start, period_end)
            DO UPDATE SET
                revenue_usd = EXCLUDED.revenue_usd,
                filing_id = EXCLUDED.filing_id,
                filed_on = EXCLUDED.filed_on
            WHERE EXCLUDED.filed_on > current_revenue.filed_on
        """),
        {
            "ticker": "MSFT",
            "period_start": record["start"],
            "period_end": record["end"],
            "revenue_usd": record["val"],
            "filing_id": record["accn"],
            "filed_on": record["filed"],
        },
    )

print("Load complete.")
