"""Extract quarterly revenue from SEC Company Facts for a completed fiscal year."""

import argparse
import csv
import json
from datetime import date, timedelta
from pathlib import Path


SOURCE = Path(__file__).resolve().parent / "data/raw/MSFT/companyfacts.json"
TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"
REVENUE_TAGS = (TAG, "Revenues", "SalesRevenueNet")
ANNUAL = {"10-K", "10-K/A"}
FORMS = ANNUAL | {"10-Q", "10-Q/A"}


def revenue_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fiscal-year", type=int, default=2025)
    parser.add_argument("--tickers", nargs="+", type=str.upper, default=["MSFT"],
                        help="Company tickers (default: MSFT). Use --from-mongo for multiple companies.")
    parser.add_argument("--from-mongo", action="store_true", help="Read the latest completed SEC snapshot.")
    return parser.parse_args()


def latest_fact(facts, start, end, forms):
    matches = [
        row for row in facts
        if row.get("start") == start.isoformat() and row["end"] == end.isoformat()
        and row["form"] in forms
    ]
    if not matches:
        raise ValueError(f"No USD revenue for {start} through {end}")
    latest_date = max(row["filed"] for row in matches)
    latest = [row for row in matches if row["filed"] == latest_date]
    if len({row["val"] for row in latest}) != 1:
        raise ValueError(f"Conflicting revenue for {start} through {end} filed on {latest_date}")
    # For identical disclosures prefer the configured tag order, then accession.
    row = max(latest, key=lambda r: (-REVENUE_TAGS.index(r["tag"]), r["accn"]))
    value = row["val"]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Invalid revenue in filing {row['accn']}")
    return {key: row[key] for key in ("start", "end", "filed", "accn", "form", "val", "tag")}


def fiscal_periods(facts, fiscal_year):
    # The FY on a comparative fact describes the filing. Use the actual dates
    # to distinguish the target annual period from prior years in the same 10-K.
    annual_periods = set()
    for row in facts:
        if row["form"] not in ANNUAL or row.get("fy") != fiscal_year or row.get("fp") != "FY":
            continue
        start, end = date.fromisoformat(row["start"]), date.fromisoformat(row["end"])
        if end.year == fiscal_year and 350 <= (end - start).days + 1 <= 378:
            annual_periods.add((start, end))
    if len(annual_periods) != 1:
        raise ValueError(f"FY{fiscal_year}: expected one annual revenue period, found {sorted(annual_periods)}")
    year_start, year_end = annual_periods.pop()

    ends = []
    start = year_start
    for quarter in (1, 2, 3):
        candidates = {
            date.fromisoformat(row["end"]) for row in facts
            if row["start"] == start.isoformat() and row["form"] in FORMS
        }
        candidates = {end for end in candidates if end < year_end and 77 <= (end - start).days + 1 <= 105}
        if len(candidates) != 1:
            raise ValueError(f"FY{fiscal_year} Q{quarter}: ambiguous or missing quarter from {start}")
        end = candidates.pop()
        ends.append(end)
        start = end + timedelta(days=1)
    if not 77 <= (year_end - start).days + 1 <= 105:
        raise ValueError(f"Unexpected fourth-quarter duration: {start} through {year_end}")
    return year_start, [*ends, year_end]


def fourth_quarter(ticker, start, end, annual, nine_months, earlier_rows):
    derived = annual["val"] - nine_months["val"]
    nine_month_delta = sum(row["revenue_usd"] for row in earlier_rows) - nine_months["val"]
    if derived < 0:
        raise ValueError(f"{ticker}: annual revenue below nine-month revenue")
    inputs = {"annual": annual, "nine_months": nine_months}
    reference = Path(__file__).resolve().parent / "data/reference/quarterly_revenue_releases.csv"
    with reference.open(newline="") as source:
        matches = [r for r in csv.DictReader(source) if
                   (r["ticker"], r["start"], r["end"]) == (ticker, start.isoformat(), end.isoformat())]
    if not matches:
        if nine_month_delta:
            raise ValueError(f"{ticker}: Q1–Q3 disagree with nine-month revenue; verify the earnings release")
        return derived, annual, inputs, {}

    release, = matches
    release.pop("ticker")
    release.update(val=int(release["val"]), form="8-K", exhibit="99.1")
    q4_delta = release["val"] - derived
    annual_delta = nine_month_delta + q4_delta
    # These reviewed releases present dollars in millions. Larger discrepancies
    # require fresh review of the cited filings before changing a stored value.
    if max(abs(nine_month_delta), abs(q4_delta), abs(annual_delta)) > 1_000_000:
        raise ValueError(f"{ticker}: revenue differs beyond the reviewed million-dollar rounding range")
    inputs["reported"] = release
    checks = {"method": "reported_earnings_release", "reconciliation_usd": {
        "q1_to_q3_minus_nine_months": nine_month_delta,
        "reported_q4_minus_derived_q4": q4_delta,
        "four_quarters_minus_annual": annual_delta,
    }}
    return release["val"], release, inputs, checks


def quarterly_revenue(fiscal_year, from_mongo=False, ticker="MSFT"):
    if from_mongo:
        from sec_companyfacts import mongo_revenue_concepts

        concepts = mongo_revenue_concepts(ticker, REVENUE_TAGS)
    else:
        if ticker != "MSFT":
            raise ValueError("Use --from-mongo for tickers other than MSFT.")
        with SOURCE.open() as source:
            company = json.load(source)
        if int(company["cik"]) != 789019:
            raise ValueError("Expected Microsoft's SEC Company Facts response")
        gaap = company["facts"]["us-gaap"]
        concepts = {tag: gaap[tag]["units"].get("USD", []) for tag in REVENUE_TAGS if tag in gaap}
    facts = [dict(row, tag=tag) for tag, records in concepts.items() for row in records if row.get("start")]
    start, ends = fiscal_periods(facts, fiscal_year)
    year_start = start
    rows = []
    for quarter, end in enumerate(ends, 1):
        checks = {}
        if quarter == 4:
            annual = latest_fact(facts, year_start, end, ANNUAL)
            nine_months = latest_fact(facts, year_start, ends[2], FORMS)
            amount, primary, inputs, checks = fourth_quarter(ticker, start, end, annual, nine_months, rows)
        else:
            primary = latest_fact(facts, start, end, FORMS)
            amount = primary["val"]
            inputs = {"reported": primary}
        sources = {"unit": "USD", "inputs": inputs, **checks}
        if "tag" in primary:
            # Use the existing compact representation when inputs share a tag.
            sources.update(taxonomy="us-gaap", tag=primary["tag"])
            for fact in inputs.values():
                if fact.get("tag") == sources["tag"]:
                    del fact["tag"]
        else:
            for key in ("annual", "nine_months"):
                inputs[key]["taxonomy"] = "us-gaap"
        rows.append({
            "ticker": ticker, "period_start": start, "period_end": end,
            "revenue_usd": amount, "filing_id": primary["accn"], "filed_on": primary["filed"],
            "source_facts": sources,
        })
        start = end + timedelta(days=1)
    return rows


if __name__ == "__main__":
    args = revenue_arguments()
    for ticker in dict.fromkeys(args.tickers):
        for row in quarterly_revenue(args.fiscal_year, args.from_mongo, ticker):
            print(f"{ticker} {row['period_start']} to {row['period_end']}: ${row['revenue_usd']:,}")
