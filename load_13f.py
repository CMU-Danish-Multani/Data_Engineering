"""Load a modern SEC 13F filing window into PostgreSQL."""

import argparse
import csv
import hashlib
import io
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


DEFAULT_WINDOW = "01jun2025-31aug2025_form13f.zip"
BASE = "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
FIELDS = {
    "SUBMISSION": "ACCESSION_NUMBER FILING_DATE SUBMISSIONTYPE CIK PERIODOFREPORT".split(),
    "COVERPAGE": "ACCESSION_NUMBER REPORTCALENDARORQUARTER ISAMENDMENT AMENDMENTNO AMENDMENTTYPE FILINGMANAGER_NAME REPORTTYPE".split(),
    "INFOTABLE": ("ACCESSION_NUMBER INFOTABLE_SK NAMEOFISSUER TITLEOFCLASS CUSIP FIGI VALUE SSHPRNAMT "
                  "SSHPRNAMTTYPE PUTCALL INVESTMENTDISCRETION OTHERMANAGER VOTING_AUTH_SOLE "
                  "VOTING_AUTH_SHARED VOTING_AUTH_NONE").split(),
}


def copy_member(conn, archive, table, download_id, cusips):
    fields = FIELDS[table]
    member, = (n for n in archive.namelist() if Path(n).name.upper() == table + ".TSV")
    scanned = kept = 0
    with archive.open(member) as stream, io.TextIOWrapper(stream, encoding="utf-8-sig", newline="") as lines:
        reader = csv.reader(lines, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        indices = [header.index(field) for field in fields]
        cusip_index = header.index("CUSIP") if table == "INFOTABLE" else None
        # Table and column names come only from FIELDS, never from archive or CLI input.
        query = f"COPY dev.f13_{table.lower()} (download_id,source_row,{','.join(fields).lower()}) FROM STDIN"
        with conn.connection.driver_connection.cursor() as cursor, cursor.copy(query) as copy:
            for scanned, row in enumerate(reader, 1):
                if len(row) != len(header):
                    raise ValueError(f"{member}, record {scanned}: unexpected field count")
                if cusip_index is not None and row[cusip_index].strip().upper() not in cusips:
                    continue
                copy.write_row((download_id, scanned, *(row[i] for i in indices)))
                kept += 1
    if not scanned:
        raise ValueError(f"{member} contains no data records")
    return scanned, kept


def load(path, source_url, engine):
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    with engine.begin() as conn:
        # Serialize retries for this filing window. Archive, rows and counts commit together.
        conn.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:url, 0))"), {"url": source_url})
        existing = conn.execute(text("""
            SELECT sha256, info_rows_scanned, info_rows_matched FROM dev.f13_downloads WHERE source_url=:url
        """), {"url": source_url}).first()
        if existing:
            if existing.sha256 != digest:
                raise ValueError("SEC archive contents changed for this URL; review the revision before importing")
            print(f"Already loaded: {existing.info_rows_matched:,} of {existing.info_rows_scanned:,} holdings lines")
            return
        download_id = conn.execute(text("""
            INSERT INTO dev.f13_downloads (source_url, sha256, archive_zip)
            VALUES (:url, :sha, :raw) RETURNING id
        """), {"url": source_url, "sha": digest, "raw": raw}).scalar_one()
        cusips = set(conn.scalars(text("SELECT cusip FROM dev.f13_securities")))
        if not cusips:
            raise ValueError("Missing 13F security mappings")
        with ZipFile(io.BytesIO(raw)) as archive:
            for table in FIELDS:
                scanned, kept = copy_member(conn, archive, table, download_id, cusips)
                print(f"{table}: selected {kept:,} of {scanned:,} rows", flush=True)
                if table == "INFOTABLE":
                    conn.execute(text("""
                        UPDATE dev.f13_downloads SET info_rows_scanned=:scanned, info_rows_matched=:kept WHERE id=:id
                    """), {"id": download_id, "scanned": scanned, "kept": kept})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window", default=DEFAULT_WINDOW, help="SEC ZIP filename for a modern filing window")
    parser.add_argument("--archive", type=Path, help="Use an already-downloaded ZIP with the same filename")
    args = parser.parse_args()
    match = re.fullmatch(r"[0-9]{2}[a-z]{3}(20[0-9]{2})-[0-9]{2}[a-z]{3}20[0-9]{2}_form13f\.zip", args.window)
    if not match or int(match[1]) < 2024:
        parser.error("Use a 2024-or-later SEC filing window (reported values are in dollars)")
    if args.archive and args.archive.name != args.window:
        parser.error("--archive filename must match --window")
    load_dotenv(Path(__file__).resolve().parent / "src/stock_db/alembic_migration/.env")
    if not os.getenv("DATABASE_URL"):
        parser.error("Set DATABASE_URL to the URL used by Alembic")
    engine = create_engine(os.environ["DATABASE_URL"])
    url = BASE + args.window
    if args.archive:
        load(args.archive, url, engine)
        return
    if not os.getenv("SEC_USER_AGENT"):
        parser.error("Set SEC_USER_AGENT to the team name and contact email")
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / args.window
        with urlopen(Request(url, headers={"User-Agent": os.environ["SEC_USER_AGENT"]}), timeout=90) as r, path.open("wb") as out:
            shutil.copyfileobj(r, out)
        load(path, url, engine)


if __name__ == "__main__":
    main()
