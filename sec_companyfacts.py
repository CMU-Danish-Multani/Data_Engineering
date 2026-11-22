"""Ingest the tracked companies' SEC Company Facts into MongoDB."""

import argparse
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from bson.decimal128 import Decimal128
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne
from sqlalchemy import create_engine, text


ENV_FILE = Path(__file__).resolve().parent / "src/stock_db/alembic_migration/.env"


def mongo_client():
    load_dotenv(ENV_FILE)
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise SystemExit("Set MONGODB_URI to your MongoDB connection URI.")
    return MongoClient(uri, serverSelectionTimeoutMS=10000)


def ingest(db, ticker, cik, url, raw, acquired_at):
    company = json.loads(raw, parse_float=Decimal128)
    if str(company["cik"]).zfill(10) != cik or not company.get("facts"):
        raise ValueError(f"{ticker}: unexpected CIK or empty Company Facts response")

    digest = hashlib.sha256(raw).hexdigest()
    snapshot = f"{cik}:{digest}"
    # Publish the manifest last so readers only see complete snapshots.
    manifests = db.companyfacts_snapshots
    if manifests.find_one({"_id": snapshot}, {"_id": 1}):
        return

    writes = []
    for taxonomy, concepts in company["facts"].items():
        for tag, concept in concepts.items():
            writes.append(UpdateOne(
                {"_id": f"{snapshot}/{taxonomy}/{tag}"},
                {"$setOnInsert": {"snapshot": snapshot, "ticker": ticker,
                                  "taxonomy": taxonomy, "tag": tag, "concept": concept}},
                upsert=True,
            ))
    if not writes:
        raise ValueError(f"{ticker}: no concepts in Company Facts response")
    db.companyfacts_concepts.bulk_write(writes, ordered=False)
    manifests.update_one({"_id": snapshot}, {"$setOnInsert": {
        "ticker": ticker, "cik": cik, "source_url": url, "acquired_at": acquired_at,
        "sha256": digest, "source_bytes": len(raw), "concept_count": len(writes),
        "source_metadata": {k: v for k, v in company.items() if k != "facts"},
    }}, upsert=True)


def mongo_revenue_facts(ticker, tag):
    with mongo_client() as client:
        db = client.get_default_database("stock_intelligence")
        latest = db.companyfacts_snapshots.find_one(
            {"ticker": ticker}, sort=[("acquired_at", -1), ("_id", -1)]
        )
        if latest is None:
            raise ValueError(f"No completed SEC snapshot for {ticker}")
        concept = db.companyfacts_concepts.find_one(
            {"_id": f"{latest['_id']}/us-gaap/{tag}"}, {"concept.units.USD": 1}
        )
        if concept is None:
            raise ValueError(f"No {tag} in {ticker} snapshot {latest['_id']}")
        return concept["concept"]["units"]["USD"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", help="Limit ingestion to one ticker in dev.companies.")
    parser.add_argument("--source-dir", type=Path,
                        help="Read saved <ticker>/companyfacts.json files instead of downloading.")
    args = parser.parse_args()
    load_dotenv(ENV_FILE)
    agent = os.getenv("SEC_USER_AGENT")
    if not args.source_dir and not agent:
        parser.error("Set SEC_USER_AGENT to the team name and contact email.")
    if not os.getenv("DATABASE_URL"):
        parser.error("Set DATABASE_URL to the PostgreSQL database containing dev.companies.")
    query = "SELECT ticker, cik FROM dev.companies"
    if args.ticker:
        query += " WHERE ticker = :ticker"
    with create_engine(os.environ["DATABASE_URL"]).connect() as conn:
        companies = conn.execute(text(query + " ORDER BY ticker"),
                                 {"ticker": (args.ticker or "").upper()}).all()
    if not companies:
        parser.error("No matching companies in dev.companies.")

    with mongo_client() as client:
        db = client.get_default_database("stock_intelligence")
        for ticker, cik in companies:
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            if args.source_dir:
                path = args.source_dir / ticker / "companyfacts.json"
                acquired = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                raw = path.read_bytes()
            else:
                time.sleep(0.25)
                acquired = datetime.now(timezone.utc)
                with urlopen(Request(url, headers={"User-Agent": agent}), timeout=60) as response:
                    raw = response.read()
            ingest(db, ticker, cik, url, raw, acquired)
            print(f"{ticker}: verified snapshot {hashlib.sha256(raw).hexdigest()[:12]} ({len(raw):,} bytes)")


if __name__ == "__main__":
    main()
