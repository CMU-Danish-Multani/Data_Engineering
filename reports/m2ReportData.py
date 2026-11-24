"""Read-only queries that supply every number in the Milestone 2 report.

Numbers in the report are never typed by hand: buildM2Report.py formats the
dictionary returned by gather(). Prints no secrets.
"""

import csv
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def scalar(conn, sql):
    return conn.execute(text(sql)).scalar()


def rows(conn, sql):
    return conn.execute(text(sql)).all()


def postgres_numbers(conn) -> dict:
    d = {}
    d["companies"] = scalar(conn, "SELECT count(*) FROM dev.companies")
    d["quarters"] = scalar(conn, "SELECT count(*) FROM final.company_financials_quarterly")
    d["first_fy"], d["last_fy"] = rows(conn, "SELECT min(fiscal_year), max(fiscal_year) FROM final.company_financials_quarterly")[0]
    d["alembic"] = scalar(conn, "SELECT version_num FROM public.alembic_version")
    d["db_mb"] = scalar(conn, "SELECT pg_database_size(current_database())") / 1e6
    d["release_q4"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_revenue WHERE source_facts->>'method' = 'reported_earnings_release'")
    d["revenue_max_recon"] = scalar(conn, """SELECT max(abs(v::numeric)) FROM dev.quarterly_revenue,
        jsonb_each_text(source_facts->'reconciliation_usd') AS r(k, v)""")
    d["oi_reported"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_operating_income WHERE source_facts->>'method' = 'reported'")
    d["oi_derived"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_operating_income WHERE source_facts->>'method' <> 'reported'")
    d["ocf_mismatch"] = scalar(conn, """SELECT count(*) FROM (
        SELECT f.ticker, f.fiscal_year, sum(o.operating_cash_flow_usd)
             - max((o.source_facts #>> '{current_ytd,val}')::bigint) FILTER (WHERE f.fiscal_quarter = 4) AS diff
        FROM final.company_financials_quarterly f
        JOIN dev.quarterly_operating_cash_flow o USING (ticker, period_start, period_end)
        GROUP BY 1, 2) t WHERE diff <> 0""")
    d["company_years"] = scalar(conn, "SELECT count(DISTINCT (ticker, fiscal_year)) FROM final.company_financials_quarterly")
    d["negative_ocf_quarters"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_operating_cash_flow WHERE operating_cash_flow_usd < 0")
    # Prices
    d["price_downloads"] = scalar(conn, "SELECT count(*) FROM dev.stock_price_downloads")
    d["price_raw"] = scalar(conn, "SELECT count(*) FROM dev.raw_stock_prices")
    d["price_flagged"] = scalar(conn, "SELECT count(quality_issue) FROM dev.raw_stock_prices")
    d["price_clean"] = scalar(conn, "SELECT count(*) FROM dev.stock_prices_daily")
    d["price_per_ticker"] = scalar(conn, "SELECT max(n) FROM (SELECT count(*) n FROM dev.stock_prices_daily GROUP BY ticker) t")
    d["price_first"], d["price_last"] = rows(conn, "SELECT min(trade_date), max(trade_date) FROM dev.stock_prices_daily")[0]
    d["price_mb"] = scalar(conn, "SELECT sum(octet_length(response_body)) FROM dev.stock_price_downloads") / 1e6
    d["price_overlap_diff"] = scalar(conn, """SELECT count(*) FROM dev.raw_stock_prices a
        JOIN dev.stock_price_downloads da USING (snapshot_id)
        JOIN dev.raw_stock_prices b ON b.trade_date = a.trade_date AND b.snapshot_id <> a.snapshot_id
        JOIN dev.stock_price_downloads db ON db.snapshot_id = b.snapshot_id AND db.ticker = da.ticker
        WHERE da.first_seen < db.first_seen AND abs(a.close::numeric - b.close::numeric) > 0.0001""")
    d["price_dup_rows"] = d["price_raw"] - d["price_clean"]
    # 13F
    d["f13_windows"] = scalar(conn, "SELECT count(*) FROM dev.f13_downloads")
    d["f13_scanned"] = scalar(conn, "SELECT sum(info_rows_scanned) FROM dev.f13_downloads")
    d["f13_kept"] = scalar(conn, "SELECT sum(info_rows_matched) FROM dev.f13_downloads")
    d["f13_mb"] = scalar(conn, "SELECT sum(octet_length(archive_zip)) FROM dev.f13_downloads") / 1e6
    d["f13_filings"] = scalar(conn, "SELECT count(*) FROM dev.f13_submission")
    d["f13_decisions"] = dict(rows(conn, "SELECT decision, count(*) FROM dev.f13_filing_review GROUP BY 1"))
    d["f13_quarters"] = rows(conn, """SELECT report_date, count(*) FROM dev.f13_manager_positions
        GROUP BY 1 HAVING count(*) > 10000 ORDER BY 1""")
    d["f13_pairs"] = rows(conn, """SELECT report_date, count(*) FROM dev.f13_quarterly_changes
        WHERE comparison_status = 'reported in both quarters' GROUP BY 1 HAVING count(*) > 1000 ORDER BY 1""")
    d["f13_securities"] = scalar(conn, "SELECT count(*) FROM dev.f13_securities")
    # Valuation
    d["val_status"] = dict(rows(conn, "SELECT valuation_status, count(*) FROM final.valuation_quarterly GROUP BY 1"))
    d["val_rows"] = scalar(conn, "SELECT count(*) FROM final.valuation_quarterly")
    d["val_annual"] = scalar(conn, "SELECT count(*) FROM final.valuation_annual")
    d["meta_no_debt"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_valuation_inputs WHERE debt_method = 'no_debt_line_in_filing'")
    d["implied_shares"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_valuation_inputs WHERE shares_method = 'net_income_divided_by_diluted_eps'")
    d["q4_eps_mismatch"] = scalar(conn, """SELECT count(*) FROM final.valuation_annual a
        JOIN dev.quarterly_valuation_inputs v USING (ticker, period_start, period_end)
        WHERE abs(a.ttm_eps - (v.source_facts #>> '{eps,val}')::numeric / (v.source_facts->>'split_factor_eps')::numeric) > 0.0001""")
    # Product KPIs
    d["prod_rows"] = scalar(conn, "SELECT count(*) FROM dev.quarterly_product_kpis")
    d["prod_values"] = scalar(conn, "SELECT count(value) FROM dev.quarterly_product_kpis")
    d["prod_view_rows"] = scalar(conn, "SELECT count(*) FROM final.product_kpis_quarterly")
    d["prod_cover"] = {(t, k): n for t, k, n in rows(conn, """SELECT ticker, kpi, count(value)
        FROM dev.quarterly_product_kpis GROUP BY 1, 2""")}
    pairs = rows(conn, """SELECT count(*), count(*) FILTER (WHERE c.value <> p.value)
        FROM dev.quarterly_product_kpis c
        JOIN final.financial_metrics_quarterly fc USING (ticker, period_start, period_end)
        JOIN final.financial_metrics_quarterly fp ON fp.ticker = fc.ticker AND fp.fiscal_year = fc.fiscal_year + 1
             AND fp.fiscal_quarter = fc.fiscal_quarter
        JOIN dev.quarterly_product_kpis p ON (p.ticker, p.period_start, p.period_end) = (fp.ticker, fp.period_start, fp.period_end)
             AND p.kpi = replace(c.kpi, '_revenue_usd', '_revenue_prior_year_usd')
        WHERE c.kpi IN ('aws_revenue_usd', 'google_cloud_revenue_usd') AND c.value IS NOT NULL AND p.value IS NOT NULL""")[0]
    d["prior_pairs"], d["prior_diff"] = pairs
    # Example row: MSFT FY2025 Q4
    d["msft"] = rows(conn, """SELECT revenue_usd, capex_usd, operating_margin_pct, operating_cash_flow_usd, free_cash_flow_usd
        FROM final.company_financials_quarterly WHERE ticker = 'MSFT' AND fiscal_year = 2025 AND fiscal_quarter = 4""")[0]
    return d


def mongo_numbers(db) -> dict:
    d = {"snapshots": db.companyfacts_snapshots.count_documents({}),
         "concepts": db.companyfacts_concepts.count_documents({}),
         "releases": db.earnings_releases.count_documents({})}
    d["facts_mb"] = sum(s["source_bytes"] for s in db.companyfacts_snapshots.find({}, {"source_bytes": 1})) / 1e6
    d["releases_mb"] = sum(s["source_bytes"] for s in db.earnings_releases.find({}, {"source_bytes": 1})) / 1e6
    d["release_quarters"] = len(db.earnings_releases.distinct("period_end"))
    d["release_extra"] = d["releases"] - len({(r["ticker"], r["period_end"]) for r in
                                               db.earnings_releases.find({}, {"ticker": 1, "period_end": 1})})
    return d


def split_pairs() -> int:
    from load_valuation_inputs import EPS, as_decimal, check_split_basis, read_splits
    from sec_companyfacts import mongo_unit_concepts
    splits = read_splits()
    return sum(check_split_basis(t, splits.get(t, []), as_decimal(mongo_unit_concepts(t, "us-gaap", (EPS,), "USD/shares")[EPS]))
               for t in ("AMZN", "GOOGL", "META", "MSFT", "NVDA"))


def gather() -> dict:
    load_dotenv(ROOT / "src/stock_db/alembic_migration/.env")
    with create_engine(os.environ["DATABASE_URL"]).connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        d = postgres_numbers(conn)
    with MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=10000) as client:
        d.update(mongo_numbers(client.get_default_database("stock_intelligence")))
    d["split_pairs"] = split_pairs()
    with (ROOT / "data/reference/capex_filing_lines.csv").open(encoding="utf-8") as f:
        d["capex_ref_lines"] = sum(1 for _ in csv.DictReader(f))
    with (ROOT / "data/reference/operating_income_releases.csv").open(encoding="utf-8") as f:
        d["oi_ref_lines"] = sum(1 for _ in csv.DictReader(f))
    return d


if __name__ == "__main__":
    for key, value in gather().items():
        print(key, "=", value)
