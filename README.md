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

## Quarterly capital expenditure

Load the revenue quarters for the same tickers and years first. They supply
the fiscal calendar and the denominator for CapEx as a percentage of revenue.
After applying the Alembic migrations, run:

```bash
uv run load_capex.py --start-year 2019 --end-year 2025
```

The loader reads USD cash purchases from the investing section of each
company's cash-flow statement. It selects year-to-date 10-Q and full-year
10-K figures for the specified reporting year (including amendments). This
keeps subsequent years' comparative presentations out of the differences.
SEC submissions metadata identifies the original reporting period for each
filing accession. The loader uses the configured `SEC_USER_AGENT` to read it.
When the original cash-flow line is missing from the selected Company Facts
tags, reviewed NVIDIA filing lines in
`data/reference/capex_filing_lines.csv` supply that cumulative amount.
Each row links to the original SEC statement. Cash outflows are stored as
positive dollars. Q1 uses its reported total. Q2 through Q4 subtract the
preceding cumulative amount. Both inputs are available in
`dev.quarterly_capex.source_facts`.

These are consolidated purchases. NVIDIA's line also includes intangible
assets. Amazon uses gross purchases before proceeds and incentives. The
metric excludes separately reported finance-lease principal repayments.
Users comparing companies or years should consider differences in filing
presentation. Different fiscal years can cover different calendar months.

```sql
SELECT ticker, period_end, capex_usd, round(capex_growth_yoy_pct, 2) AS growth_pct,
       round(capex_pct_of_revenue, 2) AS revenue_pct
FROM final.capital_expenditure_quarterly
WHERE fiscal_year = 2025 AND fiscal_quarter = 4
ORDER BY ticker;
```

## Quarterly operating margin

After applying the migrations and loading the revenue quarters, run:

```bash
uv run load_operating_income.py --start-year 2019 --end-year 2025
```

The loader reads consolidated GAAP operating income (or loss) from the SEC
Company Facts snapshot in MongoDB. SEC filing metadata identifies each
10-Q or 10-K's own reporting period. It uses the directly reported quarter
when available and checks it against the change in year-to-date income.
For FY2019–FY2025 the 35 linked Q4 GAAP earnings releases in
`data/reference/operating_income_releases.csv` provide an additional check
or supply the reported Q4 when the annual filing gives only a full-year total.
Without a reported quarter the loader subtracts the preceding cumulative total.
Signed differences up to $1 million are retained with the source filings
in `dev.quarterly_operating_income.source_facts`. Larger differences stop
the load. All years in one run are written in a single transaction.

`final.company_financials_quarterly` joins operating income, revenue and
capital expenditure on the same ticker and exact fiscal dates. Operating
margin is 100 times operating income divided by the project's stored revenue
for that quarter. Negative operating income yields a negative margin.
A missing input or zero revenue yields NULL.

```sql
SELECT ticker, fiscal_year, fiscal_quarter, operating_income_usd, revenue_usd,
       round(operating_margin_pct, 2) AS operating_margin_pct
FROM final.company_financials_quarterly
WHERE fiscal_year = 2025 AND fiscal_quarter = 4
ORDER BY ticker;
```

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

## Institutional holdings (Form 13F)

After applying the Alembic migrations, run `uv run load_13f.py`. The default
SEC download covers filings submitted June–August 2025. Use `--window` for
another supported filing window, or add `--archive /path/to/the-same-filename.zip`
to replay a saved ZIP. The loader uses `SEC_USER_AGENT` and `DATABASE_URL`.

`dev.f13_downloads` keeps the exact ZIP, its source URL, SHA-256 and counts.
`dev.f13_submission` and `dev.f13_coverpage` preserve filing fields; the
`dev.f13_infotable` rows cover the six tracked CUSIPs, including both listed
Alphabet share classes. Source row numbers begin at 1 after each TSV header.
A repeated load of an identical archive reuses the existing records.

`dev.f13_holdings_as_filed` joins each position to the manager and reporting
period by filing accession. Filter by `report_date` when comparing periods.
`ticker` identifies the issuer and `security_ticker` the share class.
For ordinary share positions select `quantity_type = 'SH' AND put_call IS NULL`.
This view retains original filings and amendments as separate disclosures.
Reconcile restatements and additions before summing across filings.

### Compare 13F share positions across quarters

Load the March–May and June–August 2025 SEC filing windows to compare the
March 31 and June 30 reporting dates. To add the earlier window:

```bash
uv run load_13f.py --window 01mar2025-31may2025_form13f.zip
```

After applying Alembic migrations, this query compares Microsoft share counts:

```sql
SELECT manager_name, previous_shares, reported_shares, change_in_reported_shares
FROM dev.f13_quarterly_changes
WHERE report_date = DATE '2025-06-30' AND security_ticker = 'MSFT'
  AND comparison_status = 'reported in both quarters'
ORDER BY manager_name;
```

The view compares consecutive calendar quarter-ends by manager CIK and security
CUSIP, including Alphabet's two classes separately. It uses public filings in
the downloaded windows; later amendments can change results. Following the
[SEC amendment guidance (questions 58b–c)](https://www.sec.gov/rules-regulations/staff-guidance/frequently-asked-questions-about-form-13f),
the latest full restatement replaces the earlier filings. Subsequent numbered
new-holdings amendments supplement it (or the original). Inspect
`dev.f13_filing_review` for each accession's disposition, including notice
filings, missing baselines, and ambiguous amendment sequences.

`dev.f13_manager_positions` sums as-reported share quantities for each
resolved manager-quarter and security, excluding put/call and principal-amount
rows. An absent share disclosure is NULL. The comparison labels one-sided
disclosures and calculates a share change only when valid counts exist on
both sides. Changes are in reported units, without split adjustments.

### Fiscal-quarter revenue for the five companies

```bash
uv run load_revenue.py --from-mongo --fiscal-year 2024 --tickers MSFT AMZN GOOGL META NVDA
uv run load_revenue.py --from-mongo --fiscal-year 2025 --tickers MSFT AMZN GOOGL META NVDA
```

This loads a completed fiscal year per company in one PostgreSQL transaction.
The extractor identifies fiscal-year boundaries from annual revenue facts and
uses actual reported quarter dates, including NVIDIA's week-based year.
It checks whole-company USD revenue across supported US-GAAP tags and selects
the latest disclosure for the exact period. Q4 normally uses annual revenue
minus the first nine months. For Alphabet FY2025 and Meta FY2024 and FY2025, the published
million-dollar figures have small reconciliation differences. The verified
Q4 earnings-release rows in
`data/reference/quarterly_revenue_releases.csv` supply the directly reported
values. Their source URLs, filing IDs, and signed reconciliation differences
are retained in the PostgreSQL row's `source_facts`. Use the annual filing
value for annual revenue. Different companies' FY2025 periods end on
different dates.

After applying the migrations, compare each company's fiscal quarters in PostgreSQL:

```sql
SELECT ticker, fiscal_quarter, period_end, prior_year_period_end,
       revenue_usd, prior_year_revenue_usd, round(revenue_growth_yoy_pct, 2) AS growth_pct
FROM final.financial_metrics_quarterly
WHERE fiscal_year = 2025
ORDER BY ticker, fiscal_quarter;
```

The view publishes fiscal years with four consecutive quarters covering the
annual filing period. It labels quarters in date order within that period and
compares each with the same company's matching fiscal quarter one year earlier.
Growth is NULL when the prior year is missing or prior revenue is zero.
