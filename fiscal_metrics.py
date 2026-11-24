"""Shared SEC filing metadata and transaction handling for quarterly metrics."""

import csv
import json
import os
import time
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

from sec_companyfacts import ENV_FILE, mongo_usd_concepts


def read_filing_references(path):
    refs = {}
    with path.open(newline="") as source:
        for row in csv.DictReader(source):
            key = (row.pop("ticker"), row["start"], row["end"])
            if key in refs:
                raise ValueError(f"Duplicate filing reference for {key}")
            row["val"] = int(row["val"])
            refs[key] = row
    return refs


def filing_periods(cik, first_year):
    """Map accessions to their own report dates, excluding comparative columns."""
    base = "https://data.sec.gov/submissions/"

    def fetch(filename):
        time.sleep(0.2)
        request = Request(base + filename, headers={"User-Agent": os.environ["SEC_USER_AGENT"]})
        with urlopen(request, timeout=45) as response:
            return json.load(response)

    filings = fetch(f"CIK{str(cik).zfill(10)}.json")["filings"]
    pages = [filings["recent"]]
    for page in filings["files"]:
        # An early fiscal quarter may end in the previous calendar year.
        if page["filingTo"] >= f"{first_year - 1}-01-01":
            pages.append(fetch(page["name"]))
    dates = {}
    for page in pages:
        for accn, end, form in zip(page["accessionNumber"], page["reportDate"], page["form"], strict=True):
            if form in ("10-Q", "10-Q/A", "10-K", "10-K/A"):
                dates[accn] = end
    return dates


def load_metric(metric, start_year, end_year, tickers, tags, references, build_rows):
    # The identifiers below are internal constants. All user input is bound as data.
    if metric not in ("capex", "operating_income", "operating_cash_flow"):
        raise ValueError(f"Unsupported financial metric: {metric}")
    if start_year > end_year:
        raise ValueError("The start year must be at or before the end year")
    load_dotenv(ENV_FILE)
    upsert = text(f"""
        INSERT INTO dev.quarterly_{metric} AS old (ticker, period_start, period_end, {metric}_usd, source_facts)
        VALUES (:ticker, :period_start, :period_end, :{metric}_usd, :source_facts)
        ON CONFLICT (ticker, period_start, period_end) DO UPDATE SET
            {metric}_usd = EXCLUDED.{metric}_usd, source_facts = EXCLUDED.source_facts
        WHERE (old.{metric}_usd, old.source_facts) IS DISTINCT FROM
              (EXCLUDED.{metric}_usd, EXCLUDED.source_facts)
    """).bindparams(bindparam("source_facts", type_=JSONB))
    with create_engine(os.environ["DATABASE_URL"]).begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:name, 0))"),
                     {"name": f"dev.quarterly_{metric}"})
        company_ids = dict(conn.execute(text("SELECT ticker, cik FROM dev.companies ORDER BY ticker")).all())
        companies = list(dict.fromkeys(tickers)) if tickers else list(company_ids)
        count = 0
        for ticker in companies:
            if ticker not in company_ids:
                raise ValueError(f"Unknown company ticker: {ticker}")
            concepts = mongo_usd_concepts(ticker, tags)
            report_dates = filing_periods(company_ids[ticker], start_year)
            for year in range(start_year, end_year + 1):
                periods = conn.execute(text("""
                    SELECT fiscal_quarter, period_start, period_end
                    FROM final.financial_metrics_quarterly
                    WHERE ticker = :ticker AND fiscal_year = :year ORDER BY fiscal_quarter
                """), {"ticker": ticker, "year": year}).all()
                rows = build_rows(ticker, year, periods, concepts, references, report_dates)
                conn.execute(upsert, rows)
                count += len(rows)
    return count
