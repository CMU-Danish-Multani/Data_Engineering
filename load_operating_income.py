"""Load consolidated GAAP operating income for completed fiscal years."""

import argparse
from pathlib import Path

from fiscal_metrics import load_metric, read_filing_references


TAG = "OperatingIncomeLoss"
REFERENCE = Path(__file__).resolve().parent / "data/reference/operating_income_releases.csv"
# Historical statements in this project present amounts to the nearest million USD.
ROUNDING_USD = 1_000_000


def period_fact(records, start, end, form, report_dates):
    matches = [r for r in records if r.get("start") == start and r["end"] == end
               and report_dates.get(r["accn"]) == end and r["form"] in (form, form + "/A")]
    if not matches:
        return None
    latest = max(r["filed"] for r in matches)
    candidates = [r for r in matches if r["filed"] == latest]
    if any(isinstance(r["val"], bool) or not isinstance(r["val"], int) for r in candidates):
        raise ValueError(f"Invalid USD operating income for {start} through {end}")
    if len({r["val"] for r in candidates}) != 1:
        raise ValueError(f"Conflicting operating income for {start} through {end} filed on {latest}")
    row = max(candidates, key=lambda r: r["accn"])
    return {k: row[k] for k in ("start", "end", "val", "form", "filed", "accn")} | {"tag": TAG}


def quarterly_operating_income(ticker, year, periods, concepts, references, report_dates):
    if [p.fiscal_quarter for p in periods] != [1, 2, 3, 4]:
        raise ValueError(f"{ticker} FY{year}: load the four revenue quarters first")
    year_start = periods[0].period_start.isoformat()
    records = concepts.get(TAG, [])
    rows = []
    previous = None
    for p in periods:
        start, end = p.period_start.isoformat(), p.period_end.isoformat()
        form = "10-K" if p.fiscal_quarter == 4 else "10-Q"
        cumulative = period_fact(records, year_start, end, form, report_dates)
        if cumulative is None:
            raise ValueError(f"{ticker} FY{year} Q{p.fiscal_quarter}: missing cumulative operating income")
        quarter = cumulative if previous is None else period_fact(records, start, end, form, report_dates)
        derived = cumulative["val"] - (previous["val"] if previous else 0)
        inputs = {"current_ytd": cumulative}
        if previous:
            inputs["previous_ytd"] = previous
        if quarter:
            inputs["reported_quarter"] = quarter
        release = references.get((ticker, start, end))
        if release:
            inputs["earnings_release"] = release
            if quarter and quarter["val"] != release["val"]:
                raise ValueError(f"{ticker} {end}: filing and earnings release disagree")
        reported = quarter or release
        amount = reported["val"] if reported else derived
        difference = amount - derived
        if abs(difference) > ROUNDING_USD:
            raise ValueError(f"{ticker} {end}: operating income needs reconciliation ({difference} USD)")
        source = {"method": "reported" if reported else "difference_of_cumulative_totals",
                  "inputs": inputs, "quarter_minus_derived_usd": difference}
        rows.append(dict(ticker=ticker, period_start=p.period_start, period_end=p.period_end,
                         operating_income_usd=amount, source_facts=source))
        previous = cumulative

    annual_delta = sum(row["operating_income_usd"] for row in rows) - previous["val"]
    if abs(annual_delta) > ROUNDING_USD:
        raise ValueError(f"{ticker} FY{year}: quarters disagree with annual operating income ({annual_delta} USD)")
    rows[-1]["source_facts"]["four_quarters_minus_annual_usd"] = annual_delta
    return rows


def load(start_year, end_year, tickers=None):
    count = load_metric("operating_income", start_year, end_year, tickers, (TAG,),
                        read_filing_references(REFERENCE), quarterly_operating_income)
    print(f"Processed {count} operating-income quarters for FY{start_year}–FY{end_year}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--tickers", nargs="+", type=str.upper)
    args = parser.parse_args()
    load(args.start_year, args.end_year, args.tickers)
