"""Load cash purchases of long-lived assets for completed company fiscal years."""

import argparse
import csv
import json
import os
import time
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

from sec_companyfacts import ENV_FILE, mongo_usd_concepts


TAGS = ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
REFERENCE = Path(__file__).resolve().parent / "data/reference/capex_filing_lines.csv"


def filing_references():
    refs = {}
    with REFERENCE.open(newline="") as source:
        for row in csv.DictReader(source):
            key = (row.pop("ticker"), row["start"], row["end"])
            if key in refs:
                raise ValueError(f"Duplicate cash-flow filing reference for {key}")
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


def ytd_fact(ticker, year, quarter, start, end, concepts, references, report_dates):
    form = "10-K" if quarter == 4 else "10-Q"
    matches = []
    for tag, records in concepts.items():
        for record in records:
            if (record.get("start"), record["end"]) != (start, end):
                continue
            if report_dates.get(record["accn"]) == end and record["form"] in (form, form + "/A"):
                fact = {k: record[k] for k in ("start", "end", "val", "accn", "filed", "form")}
                matches.append(dict(fact, tag=tag))
    reference = references.get((ticker, start, end))
    if reference is not None:
        if report_dates.get(reference["accn"]) != end or reference["form"] != form:
            raise ValueError(f"{ticker} {end}: reference filing has the wrong reporting period")
        matches.append(reference)
    if not matches:
        raise ValueError(f"{ticker} FY{year} Q{quarter}: missing cumulative cash purchases")
    latest = max(f["filed"] for f in matches)
    candidates = [f for f in matches if f["filed"] == latest]
    if any(isinstance(f["val"], bool) or not isinstance(f["val"], int) or f["val"] < 0 for f in candidates):
        raise ValueError(f"{ticker} {end}: invalid cumulative cash purchases")
    if len({f["val"] for f in candidates}) != 1:
        raise ValueError(f"{ticker} {end}: conflicting cash purchases filed on {latest}")
    return max(candidates, key=lambda f: (f["accn"], "url" in f, f.get("tag", "")))


def quarterly_capex(ticker, year, periods, concepts, references, report_dates):
    if [p.fiscal_quarter for p in periods] != [1, 2, 3, 4]:
        raise ValueError(f"{ticker} FY{year}: load the four revenue quarters first")
    year_start = periods[0].period_start.isoformat()
    rows = []
    previous = None
    for period in periods:
        current = ytd_fact(ticker, year, period.fiscal_quarter, year_start,
                           period.period_end.isoformat(), concepts, references, report_dates)
        amount = current["val"]
        inputs = {"current_ytd": current}
        if previous is not None:
            inputs["previous_ytd"] = previous
            amount -= previous["val"]
        if amount < 0:
            raise ValueError(f"{ticker} {period.period_end}: cumulative purchases decreased")
        rows.append(dict(ticker=ticker, period_start=period.period_start, period_end=period.period_end,
                         capex_usd=amount, source_facts=inputs))
        previous = current
    return rows


def load(start_year, end_year, tickers=None):
    if start_year > end_year:
        raise ValueError("The start year must be at or before the end year")
    load_dotenv(ENV_FILE)
    references = filing_references()
    upsert = text("""
        INSERT INTO dev.quarterly_capex AS old (ticker, period_start, period_end, capex_usd, source_facts)
        VALUES (:ticker, :period_start, :period_end, :capex_usd, :source_facts)
        ON CONFLICT (ticker, period_start, period_end) DO UPDATE SET
            capex_usd = EXCLUDED.capex_usd, source_facts = EXCLUDED.source_facts
        WHERE (old.capex_usd, old.source_facts) IS DISTINCT FROM
              (EXCLUDED.capex_usd, EXCLUDED.source_facts)
    """).bindparams(bindparam("source_facts", type_=JSONB))
    with create_engine(os.environ["DATABASE_URL"]).begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('dev.quarterly_capex', 0))"))
        company_ids = dict(conn.execute(text("SELECT ticker, cik FROM dev.companies ORDER BY ticker")).all())
        companies = list(dict.fromkeys(tickers)) if tickers else list(company_ids)
        count = 0
        for ticker in companies:
            if ticker not in company_ids:
                raise ValueError(f"Unknown company ticker: {ticker}")
            concepts = mongo_usd_concepts(ticker, TAGS)
            report_dates = filing_periods(company_ids[ticker], start_year)
            for year in range(start_year, end_year + 1):
                periods = conn.execute(text("""
                    SELECT fiscal_quarter, period_start, period_end
                    FROM final.financial_metrics_quarterly
                    WHERE ticker = :ticker AND fiscal_year = :year ORDER BY fiscal_quarter
                """), {"ticker": ticker, "year": year}).all()
                rows = quarterly_capex(ticker, year, periods, concepts, references, report_dates)
                conn.execute(upsert, rows)
                count += len(rows)
    print(f"Processed {count} CapEx quarters for FY{start_year}–FY{end_year}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--tickers", nargs="+", type=str.upper)
    args = parser.parse_args()
    load(args.start_year, args.end_year, args.tickers)
