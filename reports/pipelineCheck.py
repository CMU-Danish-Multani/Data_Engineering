"""Read-only cross check: every expected object exists, its rows, and KPI coverage. No secrets printed."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from sqlalchemy import create_engine, text

load_dotenv(Path(sys.argv[1]) / "src/stock_db/alembic_migration/.env")
EXPECTED = """dev.companies dev.quarterly_revenue dev.quarterly_capex dev.quarterly_operating_income
dev.quarterly_operating_cash_flow dev.quarterly_valuation_inputs dev.quarterly_product_kpis
dev.stock_price_downloads dev.raw_stock_prices dev.stock_prices_daily
dev.f13_downloads dev.f13_securities dev.f13_submission dev.f13_coverpage dev.f13_infotable
dev.f13_holdings_as_filed dev.f13_filing_review dev.f13_manager_positions dev.f13_quarterly_changes
final.financial_metrics_quarterly final.capital_expenditure_quarterly final.company_financials_quarterly
final.valuation_quarterly final.valuation_annual final.product_kpis_quarterly""".split()

with create_engine(os.environ["DATABASE_URL"]).connect() as c:
    c.execute(text("SET TRANSACTION READ ONLY"))
    q = lambda s: c.execute(text(s)).all()
    print("alembic_version:", q("SELECT version_num FROM public.alembic_version"))
    for name in EXPECTED:
        kind = q(f"SELECT c.relkind FROM pg_class c WHERE c.oid = to_regclass('{name}')")
        rows = q(f"SELECT count(*) FROM {name}")[0][0] if kind else None
        print(f"{name} | {'table' if kind and kind[0][0] == 'r' else 'view' if kind else 'MISSING'} | {rows}")
    print("KPI coverage (non-null of rows):")
    for label, sql in [
        ("revenue", "SELECT count(revenue_usd), count(*) FROM final.company_financials_quarterly"),
        ("revenue_growth", "SELECT count(revenue_growth_yoy_pct), count(*) FROM final.company_financials_quarterly"),
        ("capex", "SELECT count(capex_usd), count(*) FROM final.company_financials_quarterly"),
        ("capex_growth", "SELECT count(capex_growth_yoy_pct), count(*) FROM final.company_financials_quarterly"),
        ("capex_pct_revenue", "SELECT count(capex_pct_of_revenue), count(*) FROM final.company_financials_quarterly"),
        ("operating_margin", "SELECT count(operating_margin_pct), count(*) FROM final.company_financials_quarterly"),
        ("free_cash_flow", "SELECT count(free_cash_flow_usd), count(*) FROM final.company_financials_quarterly"),
        ("pe_quarterly", "SELECT count(pe_ratio), count(*) FROM final.valuation_quarterly"),
        ("ev_to_revenue_quarterly", "SELECT count(ev_to_revenue), count(*) FROM final.valuation_quarterly"),
        ("fcf_yield_quarterly", "SELECT count(fcf_yield_pct), count(*) FROM final.valuation_quarterly"),
        ("pe_annual", "SELECT count(pe_ratio), count(*) FROM final.valuation_annual"),
        ("ev_to_revenue_annual", "SELECT count(ev_to_revenue), count(*) FROM final.valuation_annual"),
        ("fcf_yield_annual", "SELECT count(fcf_yield_pct), count(*) FROM final.valuation_annual"),
    ]:
        print(f"  {label} | {q(sql)[0][0]} of {q(sql)[0][1]}")
    for r in q("""SELECT ticker, kpi, count(value), count(*), count(yoy_growth_pct) FROM final.product_kpis_quarterly
                  GROUP BY 1, 2 ORDER BY 1, 2"""):
        print(f"  product {r[0]} {r[1]} | {r[2]} of {r[3]} | growth {r[4]}")
    print("13F report dates:", q("SELECT report_date, count(*) FROM dev.f13_manager_positions GROUP BY 1 ORDER BY 1"))
    print("13F adjacent pairs:", q("SELECT previous_report_date, report_date, count(*) FROM dev.f13_quarterly_changes GROUP BY 1, 2 ORDER BY 2"))
    print("13F downloads:", q("SELECT source_url ~ '[^/]+$', info_rows_scanned, info_rows_matched FROM dev.f13_downloads ORDER BY id"))
    print("database size:", q("SELECT pg_size_pretty(pg_database_size(current_database()))"))

db = MongoClient(os.environ["MONGODB_URI"]).get_default_database("stock_intelligence")
for name in sorted(db.list_collection_names()):
    print(f"mongo {name} | {db[name].estimated_document_count()}")
