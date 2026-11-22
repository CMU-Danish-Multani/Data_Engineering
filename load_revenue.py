import psycopg
from extract_revenue import record

with psycopg.connect("host=localhost dbname=stock_intelligence") as conn:
    conn.execute(
        """
        INSERT INTO quarterly_revenue
            (ticker, period_start, period_end, revenue_usd, filing_id, filed_on)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker, period_start, period_end)
        DO UPDATE SET
            revenue_usd = EXCLUDED.revenue_usd,
            filing_id = EXCLUDED.filing_id,
            filed_on = EXCLUDED.filed_on
        WHERE EXCLUDED.filed_on > quarterly_revenue.filed_on
        """,
        ("MSFT", record["start"], record["end"], record["val"],
         record["accn"], record["filed"]),
    )

print("Load complete.")
