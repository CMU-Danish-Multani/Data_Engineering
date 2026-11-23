"""Load daily Yahoo Finance prices for dev.companies into PostgreSQL."""

import argparse
import hashlib
import json
import os
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


PRICES = ("open", "high", "low", "close", "adj_close")


def observation(index, values, zone, start, end):
    row = {key: None if value is None else str(value) for key, value in values.items()}
    row.update(source_row=index, trade_date=None, quality_issue=None)
    issues = []
    try:
        timestamp = values["raw_timestamp"]
        if type(timestamp) is not int:
            raise ValueError
        row["trade_date"] = datetime.fromtimestamp(timestamp, zone).date()
        if not start <= row["trade_date"] < end:
            issues.append("outside requested dates")
    except (ValueError, OverflowError, OSError):
        issues.append("invalid timestamp")

    try:
        if any(type(values[key]) not in (int, float) for key in PRICES):
            raise ValueError
        prices = [Decimal(row[key]) for key in PRICES]
        if any(not value.is_finite() or value <= 0 for value in prices):
            raise ValueError
        opening, high, low, close, _ = prices
        if low > min(opening, close) or high < max(opening, close):
            issues.append("inconsistent OHLC range")
    except (TypeError, InvalidOperation, ValueError):
        issues.append("missing or invalid price")

    volume = values["volume"]
    if type(volume) is not int or not 0 <= volume < 2**63:
        issues.append("missing or invalid volume")
    row["quality_issue"] = ", ".join(issues) or None
    return row


def fetch(ticker, start, end):
    def midnight_utc(day):
        return int(datetime.combine(day, time.min, timezone.utc).timestamp())

    query = urlencode({"period1": midnight_utc(start), "period2": midnight_utc(end), "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(ticker, safe='')}?{query}"
    fetched = datetime.now(timezone.utc)
    with urlopen(Request(url, headers={"User-Agent": "CMU Stock Intelligence coursework"}), timeout=45) as response:
        body = response.read().decode("utf-8")
    chart = json.loads(body)["chart"]
    if chart.get("error") or not chart.get("result"):
        raise ValueError(f"{ticker}: no chart result for {start} through {end} (exclusive)")
    result = chart["result"][0]
    meta = result["meta"]
    if meta["symbol"] != ticker or meta["currency"] != "USD" or meta["dataGranularity"] != "1d":
        raise ValueError(f"{ticker}: unexpected symbol, currency or frequency")
    zone = ZoneInfo(meta["exchangeTimezoneName"])
    indicators = result["indicators"]
    quotes = indicators["quote"][0]
    columns = {key: quotes.get(key, []) for key in ("open", "high", "low", "close", "volume")}
    columns["adj_close"] = indicators["adjclose"][0]["adjclose"]
    columns["raw_timestamp"] = result["timestamp"]
    if not columns["raw_timestamp"]:
        raise ValueError(f"{ticker}: empty daily history")
    # Quote metadata can change intraday even when the requested history is identical.
    signature = json.dumps([url, zone.key, columns], sort_keys=True, separators=(",", ":"))
    snapshot = hashlib.sha256(signature.encode()).hexdigest()
    rows = []
    for i in range(max(len(series) for series in columns.values())):
        values = {key: series[i] if i < len(series) else None for key, series in columns.items()}
        rows.append(observation(i, values, zone, start, end))
    by_date = {}
    for row in rows:
        if row["quality_issue"] is None:
            by_date.setdefault(row["trade_date"], []).append(row)
    for same_day in by_date.values():
        if len(same_day) > 1:
            versions = {tuple(item[key] for key in (*PRICES, "volume")) for item in same_day}
            if len(versions) == 1:
                for item in same_day[1:]:
                    item["quality_issue"] = "duplicate trading date"
            else:
                for item in same_day:
                    item["quality_issue"] = "conflicting prices for trading date"
    return dict(snapshot_id=snapshot, ticker=ticker, source_url=url, fetched=fetched, body=body), rows


def save(engine, download, rows):
    with engine.begin() as conn:
        new = conn.execute(text("""
            INSERT INTO dev.stock_price_downloads
                (snapshot_id, ticker, source_url, first_seen, last_seen, response_body)
            VALUES (:snapshot_id, :ticker, :source_url, :fetched, :fetched, :body)
            ON CONFLICT (snapshot_id) DO NOTHING RETURNING snapshot_id
        """), download).scalar_one_or_none()
        if new is None:
            conn.execute(text("""
                UPDATE dev.stock_price_downloads SET last_seen = greatest(last_seen, :fetched)
                WHERE snapshot_id = :snapshot_id
            """), download)
        else:
            conn.execute(text("""
                INSERT INTO dev.raw_stock_prices
                    (snapshot_id, source_row, raw_timestamp, trade_date, open, high, low,
                     close, adj_close, volume, quality_issue)
                VALUES (:snapshot_id, :source_row, :raw_timestamp, :trade_date, :open, :high, :low,
                        :close, :adj_close, :volume, :quality_issue)
            """), [dict(row, snapshot_id=new) for row in rows])
    return new is not None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2024, 7, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2025, 7, 1), help="Exclusive end date")
    args = parser.parse_args()
    if args.start >= args.end:
        parser.error("--start must precede --end")
    load_dotenv(Path(__file__).resolve().parent / "src/stock_db/alembic_migration/.env")
    if not os.getenv("DATABASE_URL"):
        parser.error("Set DATABASE_URL to the PostgreSQL URL used by Alembic")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as conn:
        tickers = conn.scalars(text("SELECT ticker FROM dev.companies ORDER BY ticker")).all()
    if not tickers:
        raise ValueError("dev.companies contains no tracked companies")
    for ticker in tickers:
        download, rows = fetch(ticker, args.start, args.end)
        inserted = save(engine, download, rows)
        flagged = sum(row["quality_issue"] is not None for row in rows)
        if flagged == len(rows):
            raise ValueError(f"{ticker}: all {flagged} raw observations failed validation")
        print(f"{ticker}: {len(rows)} observations, {flagged} flagged, "
              f"{'new snapshot' if inserted else 'existing snapshot'}", flush=True)


if __name__ == "__main__":
    main()
