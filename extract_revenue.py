"""Extract Microsoft's fiscal quarterly revenue from a saved SEC Company Facts response."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path


SOURCE = Path(__file__).resolve().parent / "data/raw/MSFT/companyfacts.json"
TAG = "RevenueFromContractWithCustomerExcludingAssessedTax"


def fiscal_year_argument():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fiscal-year", type=int, default=2025)
    return parser.parse_args().fiscal_year


def latest_fact(facts, start, end, forms):
    matches = [
        row for row in facts
        if row.get("start") == start.isoformat() and row["end"] == end.isoformat()
        and row["form"] in forms
    ]
    if not matches:
        raise ValueError(f"No reported USD revenue for {start} through {end}")
    latest_date = max(row["filed"] for row in matches)
    latest = [row for row in matches if row["filed"] == latest_date]
    if len({row["val"] for row in latest}) != 1:
        raise ValueError(f"Conflicting revenue for {start} through {end} filed on {latest_date}")
    row = max(latest, key=lambda item: item["accn"])
    if type(row["val"]) is not int or row["val"] < 0:
        raise ValueError(f"Invalid Microsoft revenue in filing {row['accn']}")
    return {key: row[key] for key in ("start", "end", "filed", "accn", "form", "val")}


def quarterly_revenue(fiscal_year):
    with SOURCE.open() as source:
        company = json.load(source)
    if int(company["cik"]) != 789019:
        raise ValueError("Expected Microsoft's SEC Company Facts response")
    facts = company["facts"]["us-gaap"][TAG]["units"]["USD"]
    year_start = date(fiscal_year - 1, 7, 1)
    quarter_starts = [
        year_start, date(fiscal_year - 1, 10, 1), date(fiscal_year, 1, 1),
        date(fiscal_year, 4, 1), date(fiscal_year, 7, 1),
    ]
    quarter_forms = {"10-Q", "10-Q/A", "10-K", "10-K/A"}
    rows = []
    for start, next_start in zip(quarter_starts, quarter_starts[1:]):
        end = next_start - timedelta(days=1)
        if start.month == 4:
            primary = latest_fact(facts, year_start, end, {"10-K", "10-K/A"})
            nine_months = latest_fact(facts, year_start, start - timedelta(days=1), quarter_forms)
            if sum(row["revenue_usd"] for row in rows) != nine_months["val"]:
                raise ValueError(f"Q1–Q3 disagree with nine-month revenue for FY{fiscal_year}")
            amount = primary["val"] - nine_months["val"]
            if amount < 0:
                raise ValueError(f"Annual revenue is below nine-month revenue for FY{fiscal_year}")
            inputs = {"annual": primary, "nine_months": nine_months}
        else:
            primary = latest_fact(facts, start, end, quarter_forms)
            amount = primary["val"]
            inputs = {"reported": primary}
        rows.append({
            "ticker": "MSFT", "period_start": start, "period_end": end,
            "revenue_usd": amount, "filing_id": primary["accn"], "filed_on": primary["filed"],
            "source_facts": {"taxonomy": "us-gaap", "tag": TAG, "unit": "USD", "inputs": inputs},
        })
    return rows


if __name__ == "__main__":
    for row in quarterly_revenue(fiscal_year_argument()):
        print(f"MSFT {row['period_start']} to {row['period_end']}: ${row['revenue_usd']:,}")
