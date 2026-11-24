"""Load net cash from operating activities for completed company fiscal years.

Same year-to-date method as load_capex.py, but the amount keeps its sign:
operating cash flow, and therefore a single quarter, can be negative.
"""

import argparse

from fiscal_metrics import load_metric


TAGS = ("NetCashProvidedByUsedInOperatingActivities",)


def ytd_fact(ticker, year, quarter, start, end, concepts, report_dates):
    """Latest original 10-Q or 10-K fact for the exact year-to-date period."""
    form = "10-K" if quarter == 4 else "10-Q"
    matches = [
        {k: record[k] for k in ("start", "end", "val", "accn", "filed", "form")} | {"tag": tag}
        for tag, records in concepts.items() for record in records
        if (record.get("start"), record["end"]) == (start, end)
        and report_dates.get(record["accn"]) == end and record["form"] in (form, form + "/A")
    ]
    if not matches:
        raise ValueError(f"{ticker} FY{year} Q{quarter}: missing cumulative operating cash flow")
    latest = max(f["filed"] for f in matches)
    candidates = [f for f in matches if f["filed"] == latest]
    if any(isinstance(f["val"], bool) or not isinstance(f["val"], int) for f in candidates):
        raise ValueError(f"{ticker} {end}: invalid cumulative operating cash flow")
    if len({f["val"] for f in candidates}) != 1:
        raise ValueError(f"{ticker} {end}: conflicting operating cash flow filed on {latest}")
    return max(candidates, key=lambda f: (f["accn"], f["tag"]))


def quarterly_operating_cash_flow(ticker, year, periods, concepts, references, report_dates):
    if [p.fiscal_quarter for p in periods] != [1, 2, 3, 4]:
        raise ValueError(f"{ticker} FY{year}: load the four revenue quarters first")
    year_start = periods[0].period_start.isoformat()
    rows = []
    previous = None
    for period in periods:
        current = ytd_fact(ticker, year, period.fiscal_quarter, year_start,
                           period.period_end.isoformat(), concepts, report_dates)
        inputs = {"current_ytd": current}
        amount = current["val"]
        if previous is not None:
            inputs["previous_ytd"] = previous
            amount -= previous["val"]
        rows.append(dict(ticker=ticker, period_start=period.period_start, period_end=period.period_end,
                         operating_cash_flow_usd=amount, source_facts=inputs))
        previous = current
    return rows


def load(start_year, end_year, tickers=None):
    count = load_metric("operating_cash_flow", start_year, end_year, tickers, TAGS, {},
                        quarterly_operating_cash_flow)
    print(f"Processed {count} operating cash flow quarters for FY{start_year} to FY{end_year}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, required=True)
    parser.add_argument("--end-year", type=int, required=True)
    parser.add_argument("--tickers", nargs="+", type=str.upper)
    args = parser.parse_args()
    load(args.start_year, args.end_year, args.tickers)
