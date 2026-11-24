"""Store each tracked company's quarterly earnings release (8-K Item 2.02, Exhibit 99.1) in MongoDB.

One document per release in `earnings_releases`, keyed by filing accession.
The raw HTML is kept unchanged with its SHA-256; `text` is a tag-free copy in
which table cells are separated by " | " and rows by newlines. Each release is
linked to the fiscal quarter it reports: the latest quarter in
final.financial_metrics_quarterly that ends before the filing date, within 75 days.
"""

import argparse
import hashlib
import json
import os
import re
import time
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from sec_companyfacts import ENV_FILE, mongo_client


ARCHIVE = "https://www.sec.gov/Archives/edgar/data/"
EXHIBIT = re.compile(r"(ex|exhibit)[-_]?99[-_.]?0?1|ex991|dex991|991\.htm|fy\d\dpr\.htm|^pressrelease\.htm$", re.IGNORECASE)


class TextExtractor(HTMLParser):
    """Visible text with table structure kept as ' | ' cells and newline rows."""

    BLOCK = {"p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__()
        self.parts, self.skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("td", "th"):
            self.parts.append(" | ")
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def text(self):
        joined = "".join(self.parts).replace("\xa0", " ").replace("​", "")
        lines = (re.sub(r"[ \t]+", " ", line).strip(" |") for line in joined.splitlines())
        return "\n".join(line for line in lines if line)


def sec_get(url, agent):
    time.sleep(0.2)
    with urlopen(Request(url, headers={"User-Agent": agent}), timeout=60) as response:
        return response.read()


def earnings_filings(cik, agent, first, last):
    """(accession, filing date) for 8-K filings that report Item 2.02."""
    base = "https://data.sec.gov/submissions/"
    filings = json.loads(sec_get(f"{base}CIK{cik}.json", agent))["filings"]
    pages = [filings["recent"]] + [json.loads(sec_get(base + p["name"], agent))
                                   for p in filings["files"] if p["filingTo"] >= first.isoformat()]
    found = set()
    for page in pages:
        for accn, filed, form, items in zip(page["accessionNumber"], page["filingDate"], page["form"],
                                            page["items"], strict=True):
            if form == "8-K" and "2.02" in items.split(",") and first <= date.fromisoformat(filed) <= last:
                found.add((accn, filed))
    return sorted(found, key=lambda f: f[1])


def exhibit_url(cik, accn, agent):
    folder = f"{ARCHIVE}{int(cik)}/{accn.replace('-', '')}/"
    try:
        listing = sec_get(folder + "index.json", agent)
        names = [item["name"] for item in json.loads(listing)["directory"]["item"]]
    except HTTPError as error:
        if error.code != 404:
            raise
        # Some folders have no JSON listing; the filing's index page still links every document.
        page = sec_get(f"{folder}{accn}-index.htm", agent).decode("utf-8", errors="replace")
        names = [link.rsplit("/", 1)[-1] for link in re.findall(r'href="(/Archives/[^"]+)"', page)]
    matches = sorted(n for n in names if EXHIBIT.search(n) and n.lower().endswith((".htm", ".html")))
    if not matches:
        raise ValueError(f"{accn}: no Exhibit 99.1 among {names}")
    return folder + matches[0]


def fiscal_quarter(quarters, filed):
    """The quarter a release reports: latest period end before filing, at most 75 days earlier."""
    filed = date.fromisoformat(filed)
    candidates = [q for q in quarters if q.period_end < filed and (filed - q.period_end).days <= 75]
    return max(candidates, key=lambda q: q.period_end) if candidates else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", type=str.upper, default=None, help="Limit to one ticker.")
    args = parser.parse_args()
    load_dotenv(ENV_FILE)
    agent = os.environ["SEC_USER_AGENT"]
    with create_engine(os.environ["DATABASE_URL"]).connect() as conn:
        companies = conn.execute(text("SELECT ticker, cik FROM dev.companies ORDER BY ticker")).all()
        quarters = conn.execute(text("""SELECT ticker, fiscal_year, fiscal_quarter, period_start, period_end
                                        FROM final.financial_metrics_quarterly""")).all()
    with mongo_client() as client:
        releases = client.get_default_database("stock_intelligence").earnings_releases
        releases.create_index([("ticker", 1), ("period_end", 1)])
        for ticker, cik in companies:
            if args.ticker and ticker != args.ticker:
                continue
            own = [q for q in quarters if q.ticker == ticker]
            first = min(q.period_end for q in own)
            last = max(q.period_end for q in own)
            stored = skipped = 0
            for accn, filed in earnings_filings(cik, agent, first, date.fromordinal(last.toordinal() + 75)):
                quarter = fiscal_quarter(own, filed)
                if quarter is None:
                    skipped += 1
                    continue
                if releases.find_one({"_id": accn}, {"_id": 1}):
                    stored += 1
                    continue
                url = exhibit_url(cik, accn, agent)
                raw = sec_get(url, agent)
                html = raw.decode("utf-8", errors="replace")
                extractor = TextExtractor()
                extractor.feed(html)
                releases.insert_one({
                    "_id": accn, "ticker": ticker, "cik": cik, "filed": filed, "source_url": url,
                    "fiscal_year": quarter.fiscal_year, "fiscal_quarter": quarter.fiscal_quarter,
                    "period_start": quarter.period_start.isoformat(), "period_end": quarter.period_end.isoformat(),
                    "sha256": hashlib.sha256(raw).hexdigest(), "source_bytes": len(raw),
                    "fetched_at": datetime.now(timezone.utc), "html": html, "text": extractor.text(),
                })
                stored += 1
            print(f"{ticker}: {stored} releases stored, {skipped} Item 2.02 filings outside the tracked quarters", flush=True)


if __name__ == "__main__":
    main()
