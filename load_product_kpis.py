"""Extract product KPIs from the earnings releases in MongoDB into dev.quarterly_product_kpis.

One row per company, fiscal quarter and KPI. A value keeps the release URL,
accession and the exact text it was read from, which must occur in the stored
release. A KPI that the release does not state is stored as NULL with a note,
never estimated. For each quarter the latest filed release is used (earlier
Item 2.02 filings in the same window are updates or blog posts).
Table values are USD millions; text values are USD billions or millions.
"""

import argparse
import os
import re
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from sec_companyfacts import ENV_FILE, mongo_client


KPIS = {
    "AMZN": ("aws_revenue_usd", "aws_revenue_prior_year_usd", "aws_operating_income_usd"),
    "GOOGL": ("google_cloud_revenue_usd", "google_cloud_revenue_prior_year_usd", "google_cloud_operating_income_usd"),
    "META": ("family_of_apps_revenue_usd", "advertising_revenue_usd", "average_revenue_per_person_usd"),
    "MSFT": ("microsoft_cloud_revenue_usd", "azure_revenue_growth_pct", "microsoft_cloud_gross_margin_pct"),
    "NVDA": ("data_center_revenue_usd",),
}
NOT_IN_RELEASE = {
    "average_revenue_per_person_usd": "Meta does not state average revenue per person in its earnings release (Exhibit 99.1).",
}
NUMBER = re.compile(r"^\(?-?\$?[\d,]+(\.\d+)?\)?$")
SCALE = {"billion": Decimal(10) ** 9, "million": Decimal(10) ** 6}


def to_number(token):
    negative = token.startswith("(") and token.endswith(")")
    value = Decimal(token.strip("()$").replace(",", ""))
    return -value if negative else value


def row_after(lines, label, start=0, occurrence=1, stop=None):
    """First numbers of a table row whose cells may sit on one line or on the following lines."""
    seen = 0
    for i in range(start, len(lines) if stop is None else min(stop, len(lines))):
        cells = [c.strip() for c in lines[i].split("|")]
        if cells[0] != label:
            continue
        seen += 1
        if seen < occurrence:
            continue
        numbers, used = [], [lines[i]]
        tokens = cells[1:]
        j = i
        while True:
            for token in tokens:
                if NUMBER.match(token.replace(" ", "")):
                    numbers.append(to_number(token.replace(" ", "")))
            if len(numbers) >= 2 or j + 1 >= len(lines) or re.search(r"[A-Za-z]", lines[j + 1]):
                break
            j += 1
            used.append(lines[j])
            tokens = [c.strip() for c in lines[j].split("|")]
        return numbers, "\n".join(used), i
    return None, None, None


def money(match_value, unit):
    return int(Decimal(match_value.replace(",", "")) * SCALE[unit])


def amazon(lines, body):
    found = {}
    _, _, block = row_after(lines, "AWS")
    if block is not None:
        sales, sales_text, _ = row_after(lines, "Net sales", block, stop=block + 4)
        income, income_text, _ = row_after(lines, "Operating income", block, stop=block + 16)
        if sales and len(sales) >= 2:
            found["aws_revenue_prior_year_usd"] = (int(sales[0] * 10**6), sales_text, "segment table, prior-year column")
            found["aws_revenue_usd"] = (int(sales[1] * 10**6), sales_text, "segment table, current quarter")
        if income and len(income) >= 2:
            found["aws_operating_income_usd"] = (int(income[1] * 10**6), income_text, "segment table, current quarter")
    return found


def alphabet(lines, body):
    found = {}
    revenue, revenue_text, at = row_after(lines, "Google Cloud")
    if revenue and len(revenue) >= 2:
        found["google_cloud_revenue_prior_year_usd"] = (int(revenue[0] * 10**6), revenue_text, "revenue table, prior-year column")
        found["google_cloud_revenue_usd"] = (int(revenue[1] * 10**6), revenue_text, "revenue table, current quarter")
        income, income_text, _ = row_after(lines, "Google Cloud", at + 1)
        # The second Google Cloud row is operating income only once segment results are reported.
        if income and len(income) >= 2 and income[:2] != revenue[:2] and abs(income[1]) < revenue[1]:
            found["google_cloud_operating_income_usd"] = (int(income[1] * 10**6), income_text,
                                                          "segment operating income table, current quarter")
    return found


def meta(lines, body):
    found = {}
    for kpi, label in (("family_of_apps_revenue_usd", "Family of Apps"), ("advertising_revenue_usd", "Advertising")):
        numbers, source, _ = row_after(lines, label)
        if numbers:
            found[kpi] = (int(numbers[0] * 10**6), source, "revenue table, current quarter (first column)")
    return found


def microsoft(lines, body):
    found = {}
    m = re.search(r"(Microsoft Cloud|commercial cloud) revenue[^.$]{0,80}?\$([\d.,]+) billion", body, re.I)
    if m:
        note = None if m.group(1).lower() == "microsoft cloud" else "Labelled commercial cloud in this release."
        found["microsoft_cloud_revenue_usd"] = (money(m.group(2), "billion"), m.group(0), "release text", note)
    m = re.search(r"(Azure(?: and other cloud\s+services)?)\s+revenue growth of (\d+)%", body)
    if m:
        note = None if "other cloud" in m.group(1) else "Labelled Azure revenue growth in this release."
        found["azure_revenue_growth_pct"] = (Decimal(m.group(2)), m.group(0), "release text", note)
    m = re.search(r"(Microsoft Cloud|commercial cloud) gross margin percentage[^.%]{0,60}?(?:to|was) (\d+)%", body, re.I)
    if m:
        found["microsoft_cloud_gross_margin_pct"] = (Decimal(m.group(2)), m.group(0), "release text")
    return found


def nvidia(lines, body):
    m = re.search(r"data ?center revenue (?:of|was) (?:a record )?\$([\d.,]+) (billion|million)", body, re.I)
    if not m:
        m = re.search(r"^Data ?[Cc]enter\n•?\s*(?:First|Second|Third|Fourth)-quarter revenue was (?:a record )?"
                      r"\$([\d.,]+) (billion|million)", body, re.M)
    if not m:
        return {}
    return {"data_center_revenue_usd": (money(m.group(1), m.group(2)), m.group(0), "release text")}


EXTRACT = {"AMZN": amazon, "GOOGL": alphabet, "META": meta, "MSFT": microsoft, "NVDA": nvidia}


def quarter_rows(ticker, quarter, release):
    body = release["text"]
    found = EXTRACT[ticker](body.splitlines(), body)
    rows = []
    for kpi in KPIS[ticker]:
        value, source_text, method, note = None, None, None, NOT_IN_RELEASE.get(kpi)
        if kpi in found:
            value, source_text, method, *rest = found[kpi]
            note = rest[0] if rest else None
            if source_text not in body:
                raise ValueError(f"{ticker} {quarter.period_end} {kpi}: source text not found in the release")
            if kpi.endswith("revenue_usd") and not 0 < value <= quarter.revenue_usd:
                raise ValueError(f"{ticker} {quarter.period_end} {kpi}: {value} outside 0 to total revenue")
        elif note is None:
            note = "Not stated in the earnings release (Exhibit 99.1) for this quarter."
        rows.append(dict(ticker=ticker, period_start=quarter.period_start, period_end=quarter.period_end,
                         kpi=kpi, value=value, unit="pct" if kpi.endswith("_pct") else "USD",
                         source_url=release["source_url"], accession=release["_id"],
                         source_text=source_text, method=method, definition_note=note))
    return rows


def load(dry_run: bool = False) -> None:
    load_dotenv(ENV_FILE)
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        quarters = conn.execute(text("""SELECT ticker, period_start, period_end, revenue_usd
                                        FROM final.financial_metrics_quarterly ORDER BY ticker, period_end""")).all()
    rows = []
    with mongo_client() as client:
        releases = client.get_default_database("stock_intelligence").earnings_releases
        for quarter in quarters:
            release = releases.find_one({"ticker": quarter.ticker, "period_end": quarter.period_end.isoformat()},
                                        {"html": 0}, sort=[("filed", -1)])
            if release is None:
                raise ValueError(f"{quarter.ticker} {quarter.period_end}: no earnings release stored")
            rows += quarter_rows(quarter.ticker, quarter, release)
    counts = {}
    for r in rows:
        key = (r["ticker"], r["kpi"])
        counts[key] = counts.get(key, 0) + (r["value"] is not None)
    for (ticker, kpi), n in sorted(counts.items()):
        print(f"{ticker} {kpi}: {n} of 28 quarters stated")
    if dry_run:
        print(f"Dry run: {len(rows)} rows built, nothing written.")
        return
    upsert = text("""
        INSERT INTO dev.quarterly_product_kpis AS old
            (ticker, period_start, period_end, kpi, value, unit, source_url, accession, source_text, method, definition_note)
        VALUES (:ticker, :period_start, :period_end, :kpi, :value, :unit, :source_url, :accession, :source_text,
                :method, :definition_note)
        ON CONFLICT (ticker, period_start, period_end, kpi) DO UPDATE SET
            value = EXCLUDED.value, unit = EXCLUDED.unit, source_url = EXCLUDED.source_url,
            accession = EXCLUDED.accession, source_text = EXCLUDED.source_text, method = EXCLUDED.method,
            definition_note = EXCLUDED.definition_note
        WHERE (old.value, old.source_url, old.source_text, old.definition_note)
              IS DISTINCT FROM (EXCLUDED.value, EXCLUDED.source_url, EXCLUDED.source_text, EXCLUDED.definition_note)
    """)
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('dev.quarterly_product_kpis', 0))"))
        conn.execute(upsert, rows)
    print(f"Processed {len(rows)} product KPI rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Extract and print coverage without writing.")
    load(parser.parse_args().dry_run)
