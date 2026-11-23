"""Load cash purchases of long-lived assets for completed company fiscal years."""

import argparse
from pathlib import Path

from fiscal_metrics import filing_periods, load_metric, read_filing_references


TAGS = ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
REFERENCE = Path(__file__).resolve().parent / "data/reference/capex_filing_lines.csv"


def filing_references():
    return read_filing_references(REFERENCE)


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
    count = load_metric("capex", start_year, end_year, tickers, TAGS, filing_references(), quarterly_capex)
    print(f"Processed {count} CapEx quarters for FY{start_year}–FY{end_year}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--tickers", nargs="+", type=str.upper)
    args = parser.parse_args()
    load(args.start_year, args.end_year, args.tickers)
