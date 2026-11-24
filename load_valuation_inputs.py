"""Load split-adjusted diluted EPS, diluted shares, debt and cash for each fiscal quarter.

All per-share values are restated to today's share basis with
data/reference/stock_splits.csv, because Yahoo closes are split adjusted.
A fact filed before a split ex-date is divided (EPS) or multiplied (shares)
by the ratios of every later split. The split check compares each original
EPS with the restated EPS of later filings and stops on a split-sized gap.
"""

import argparse
import csv
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from bson.decimal128 import Decimal128
from dotenv import load_dotenv
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.dialects.postgresql import JSONB

from fiscal_metrics import filing_periods
from sec_companyfacts import ENV_FILE, mongo_unit_concepts


SPLITS = Path(__file__).resolve().parent / "data/reference/stock_splits.csv"
EPS = "EarningsPerShareDiluted"
SHARES = "WeightedAverageNumberOfDilutedSharesOutstanding"
NET_INCOME = "NetIncomeLoss"
CASH = "CashAndCashEquivalentsAtCarryingValue"
DEBT_TAGS = ("LongTermDebt", "LongTermDebtNoncurrent", "LongTermDebtCurrent",
             "LongTermDebtAndCapitalLeaseObligations", "CommercialPaper", "ShortTermBorrowings")
SPLIT_RATIOS = (2, 3, 4, 5, 10, 20)


def read_splits(path: Path = SPLITS) -> dict:
    splits = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            splits.setdefault(row["ticker"], []).append((date.fromisoformat(row["ex_date"]), int(row["ratio"])))
    return splits


def split_factor(splits, filed: str) -> int:
    """Shares multiplier from a filing's share basis to today's basis."""
    factor = 1
    for ex_date, ratio in splits:
        if ex_date > date.fromisoformat(filed):
            factor *= ratio
    return factor


def original_fact(records, start, end, report_dates, forms):
    """Latest fact for exact dates from a filing whose own period ends at `end`."""
    matches = [r for r in records if r.get("start") == start and r["end"] == end
               and report_dates.get(r["accn"]) == end and r["form"] in forms]
    if not matches:
        return None
    latest = max(r["filed"] for r in matches)
    candidates = [r for r in matches if r["filed"] == latest]
    if len({r["val"] for r in candidates}) != 1:
        raise ValueError(f"Conflicting facts for {start} to {end} filed on {latest}")
    row = max(candidates, key=lambda r: r["accn"])
    return {k: row[k] for k in ("start", "end", "val", "accn", "form", "filed")}


def check_split_basis(ticker, splits, records):
    """Stop when an original EPS and a later restated EPS differ by a split ratio."""
    by_period = {}
    for r in records:
        if r.get("start"):
            by_period.setdefault((r["start"], r["end"]), []).append(r)
    checked = 0
    for rows in by_period.values():
        rows.sort(key=lambda r: r["filed"])
        first = rows[0]
        if first["val"] == 0:
            continue
        base = Decimal(str(first["val"])) / split_factor(splits, first["filed"])
        for later in rows[1:]:
            restated = Decimal(str(later["val"])) / split_factor(splits, later["filed"])
            if restated == 0:
                continue
            ratio = abs(base / restated)
            if any(abs(ratio - k) < Decimal("0.05") * k or abs(ratio - Decimal(1) / k) < Decimal("0.05") / k
                   for k in SPLIT_RATIOS):
                raise ValueError(f"{ticker} {first['start']} to {first['end']}: EPS {first['val']} filed "
                                 f"{first['filed']} vs {later['val']} filed {later['filed']} differ by a split "
                                 "ratio after adjustment; check stock_splits.csv")
            checked += 1
    return checked


def period_shares(shares, net_income, eps, start, end, report_dates, forms):
    """Reported diluted weighted shares, else net income divided by diluted EPS."""
    reported = original_fact(shares, start, end, report_dates, forms)
    if reported:
        return reported, "reported_diluted_weighted_average"
    income = original_fact(net_income, start, end, report_dates, forms)
    per_share = original_fact(eps, start, end, report_dates, forms)
    if income and per_share and per_share["val"]:
        implied = dict(income, val=round(Decimal(str(income["val"])) / Decimal(str(per_share["val"]))))
        return implied, "net_income_divided_by_diluted_eps"
    return None, None


def balance_sheet(usd, end, report_dates):
    """Total debt and cash as of `end`, from the filing for that period."""
    def instant(tag):
        rows = [r for r in usd.get(tag, []) if "start" not in r and r["end"] == end
                and report_dates.get(r["accn"]) == end]
        if not rows:
            return None
        latest = max(r["filed"] for r in rows)
        values = {r["val"] for r in rows if r["filed"] == latest}
        if len(values) != 1:
            raise ValueError(f"Conflicting {tag} at {end}")
        row = max((r for r in rows if r["filed"] == latest), key=lambda r: r["accn"])
        return {k: row[k] for k in ("end", "val", "accn", "form", "filed")} | {"tag": tag}

    facts = {tag: instant(tag) for tag in (*DEBT_TAGS, CASH)}
    if facts["LongTermDebt"]:
        long_term, method = [facts["LongTermDebt"]], "LongTermDebt"
    elif facts["LongTermDebtNoncurrent"]:
        long_term = [f for f in (facts["LongTermDebtNoncurrent"], facts["LongTermDebtCurrent"]) if f]
        method = "LongTermDebtNoncurrent plus LongTermDebtCurrent"
    elif facts["LongTermDebtAndCapitalLeaseObligations"]:
        long_term, method = [facts["LongTermDebtAndCapitalLeaseObligations"]], "LongTermDebtAndCapitalLeaseObligations"
    else:
        long_term, method = [], "no_debt_line_in_filing"
    short_term = [f for f in (facts["CommercialPaper"], facts["ShortTermBorrowings"]) if f]
    if facts[CASH] is None:
        raise ValueError(f"Missing cash and cash equivalents at {end}")
    debt = sum(f["val"] for f in long_term + short_term)
    return debt, method, facts[CASH]["val"], {"debt": long_term + short_term, "cash": facts[CASH]}


def as_decimal(records):
    """Company Facts stores non-integer values as BSON Decimal128."""
    return [dict(r, val=r["val"].to_decimal()) if isinstance(r["val"], Decimal128) else r for r in records]


def company_rows(ticker, cik, periods_by_year, splits):
    eps = as_decimal(mongo_unit_concepts(ticker, "us-gaap", (EPS,), "USD/shares").get(EPS, []))
    shares = mongo_unit_concepts(ticker, "us-gaap", (SHARES,), "shares").get(SHARES, [])
    usd = mongo_unit_concepts(ticker, "us-gaap", (NET_INCOME, CASH, *DEBT_TAGS), "USD")
    checked = check_split_basis(ticker, splits.get(ticker, []), eps)
    report_dates = filing_periods(cik, min(periods_by_year))
    rows = []
    for year, periods in sorted(periods_by_year.items()):
        if [p.fiscal_quarter for p in periods] != [1, 2, 3, 4]:
            raise ValueError(f"{ticker} FY{year}: load the four revenue quarters first")
        year_start = periods[0].period_start.isoformat()
        adjusted_eps = []
        for p in periods:
            start, end = p.period_start.isoformat(), p.period_end.isoformat()
            if p.fiscal_quarter == 4:
                start, forms = year_start, ("10-K", "10-K/A")
            else:
                forms = ("10-Q", "10-Q/A")
            eps_fact = original_fact(eps, start, end, report_dates, forms)
            if eps_fact is None:
                raise ValueError(f"{ticker} FY{year} Q{p.fiscal_quarter}: missing diluted EPS")
            eps_value = Decimal(str(eps_fact["val"])) / split_factor(splits.get(ticker, []), eps_fact["filed"])
            eps_method = "reported_quarter"
            if p.fiscal_quarter == 4:
                eps_value -= sum(adjusted_eps)
                eps_method = "annual_minus_first_three_quarters"
            adjusted_eps.append(eps_value)
            share_fact, share_method = period_shares(shares, usd.get(NET_INCOME, []), eps, start, end,
                                                     report_dates, forms)
            if share_fact is None:
                raise ValueError(f"{ticker} FY{year} Q{p.fiscal_quarter}: missing diluted shares")
            share_factor = split_factor(splits.get(ticker, []), share_fact["filed"])
            debt, debt_method, cash, balance_facts = balance_sheet(usd, end, report_dates)
            rows.append(dict(
                ticker=ticker, period_start=p.period_start, period_end=p.period_end,
                diluted_eps_usd=eps_value, eps_method=eps_method,
                diluted_shares=int(share_fact["val"]) * share_factor, shares_method=share_method,
                total_debt_usd=debt, debt_method=debt_method, cash_usd=cash,
                source_facts={"eps": eps_fact | {"val": str(eps_fact["val"])},
                              "shares": share_fact | {"val": int(share_fact["val"])},
                              "split_factor_eps": split_factor(splits.get(ticker, []), eps_fact["filed"]),
                              "split_factor_shares": share_factor, **balance_facts},
            ))
    return rows, checked


def load(start_year: int, end_year: int, dry_run: bool = False) -> None:
    load_dotenv(ENV_FILE)
    splits = read_splits()
    engine = create_engine(os.environ["DATABASE_URL"])
    upsert = text("""
        INSERT INTO dev.quarterly_valuation_inputs AS old
            (ticker, period_start, period_end, diluted_eps_usd, eps_method, diluted_shares,
             shares_method, total_debt_usd, debt_method, cash_usd, source_facts)
        VALUES (:ticker, :period_start, :period_end, :diluted_eps_usd, :eps_method, :diluted_shares,
                :shares_method, :total_debt_usd, :debt_method, :cash_usd, :source_facts)
        ON CONFLICT (ticker, period_start, period_end) DO UPDATE SET
            diluted_eps_usd = EXCLUDED.diluted_eps_usd, eps_method = EXCLUDED.eps_method,
            diluted_shares = EXCLUDED.diluted_shares, shares_method = EXCLUDED.shares_method,
            total_debt_usd = EXCLUDED.total_debt_usd, debt_method = EXCLUDED.debt_method,
            cash_usd = EXCLUDED.cash_usd, source_facts = EXCLUDED.source_facts
        WHERE (old.diluted_eps_usd, old.diluted_shares, old.total_debt_usd, old.cash_usd, old.source_facts)
              IS DISTINCT FROM (EXCLUDED.diluted_eps_usd, EXCLUDED.diluted_shares, EXCLUDED.total_debt_usd,
                                EXCLUDED.cash_usd, EXCLUDED.source_facts)
    """).bindparams(bindparam("source_facts", type_=JSONB))
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('dev.quarterly_valuation_inputs', 0))"))
        companies = conn.execute(text("SELECT ticker, cik FROM dev.companies ORDER BY ticker")).all()
        periods = conn.execute(text("""
            SELECT ticker, fiscal_year, fiscal_quarter, period_start, period_end
            FROM final.financial_metrics_quarterly
            WHERE fiscal_year BETWEEN :a AND :b ORDER BY ticker, fiscal_year, fiscal_quarter
        """), {"a": start_year, "b": end_year}).all()
        all_rows = []
        for ticker, cik in companies:
            by_year = {}
            for p in periods:
                if p.ticker == ticker:
                    by_year.setdefault(p.fiscal_year, []).append(p)
            rows, checked = company_rows(ticker, cik, by_year, splits)
            methods = {}
            for r in rows:
                methods[(r["shares_method"], r["debt_method"])] = methods.get((r["shares_method"], r["debt_method"]), 0) + 1
            print(f"{ticker}: {len(rows)} quarters, {checked} restated EPS pairs passed the split check, {methods}")
            all_rows += rows
        if dry_run:
            for r in all_rows:
                if r["ticker"] in ("MSFT", "NVDA") and r["period_end"].year == 2025:
                    print(r["ticker"], r["period_end"], round(r["diluted_eps_usd"], 4), r["diluted_shares"],
                          r["total_debt_usd"], r["cash_usd"])
            print(f"Dry run: {len(all_rows)} rows built, nothing written.")
            return
        conn.execute(upsert, all_rows)
    print(f"Processed {len(all_rows)} valuation input quarters for FY{start_year} to FY{end_year}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2019)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--dry-run", action="store_true", help="Build and print rows without writing.")
    args = parser.parse_args()
    if args.start_year > args.end_year:
        parser.error("--start-year must be at or before --end-year")
    load(args.start_year, args.end_year, args.dry_run)
