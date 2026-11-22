# Data_Engineering
## SEC Company Facts ingestion

From the repository root, run `uv sync --locked`. Set `DATABASE_URL` to the
PostgreSQL URL used by Alembic, `MONGODB_URI` to the destination MongoDB
connection URI, and `SEC_USER_AGENT` to the team name and contact email.
These variables can also go in the ignored `src/stock_db/alembic_migration/.env`.

```bash
uv run sec_companyfacts.py
uv run extract_revenue.py --from-mongo --fiscal-year 2025
uv run load_revenue.py --from-mongo --fiscal-year 2025
```

The first command fetches Company Facts for each ticker in `dev.companies`.
Use `--ticker MSFT` for one company or `--source-dir data/raw` to import
saved responses from `<ticker>/companyfacts.json`. In MongoDB, each snapshot
has one document per taxonomy and concept in `companyfacts_concepts`.
`companyfacts_snapshots` records the source URL, content hash, acquisition
time and concept count after all documents have been written. Identical
responses reuse the same snapshot. The database defaults to `stock_intelligence`
when the URI omits a database name.

The second command previews Microsoft quarterly revenue from the newest
completed Microsoft snapshot. The third writes those rows to PostgreSQL
`dev.quarterly_revenue`. Omitting `--from-mongo` uses the saved Microsoft
file as before.

## Daily stock prices

Apply the Alembic migrations, then run the price loader from the repository root:

```bash
uv run alembic -c src/stock_db/alembic_migration/alembic.ini upgrade head
uv run load_stock_prices.py --start 2024-07-01 --end 2025-07-01
```

The end date is exclusive. The loader uses the Yahoo Finance daily chart feed
for the tickers in `dev.companies`. Each distinct price history retains its
original response and source URL in `dev.stock_price_downloads`. Inspect the
source rows and any validation issues in `dev.raw_stock_prices`. Trading dates
use the exchange time zone. `dev.stock_prices_daily` selects the latest valid
observation per ticker and date and exposes both close and adjusted close.
Repeated downloads with unchanged historical values reuse the existing snapshot.
