# Spec and plan: the 7 remaining KPIs, longer prices, more 13F quarters

Written 2026-11-23 by the spec-planner agent from the repository and the
user's decisions. Tagged "not checked" where a value comes from memory.
Status: draft, waiting on the open questions in section 8.

## 1. Goal

Add to the shared RDS, without changing anything that exists: free cash flow
(FCF); P/E, EV/Revenue and FCF yield, both trailing twelve months (TTM) and
annual; the product KPIs. Extend prices to 2019-01-01 through the run date.
Load 13F for at least four report dates. Every value keeps its source filing.
A missing value is NULL with a note, never invented.

## 2. Non goals (banned)

- S3 lake, staging schema, star schema rewrite.
- Airflow, cron or any scheduler.
- RAG assistant, LLM commentary, dashboard UI.
- Changing how existing loaders behave (`load_capex.py`,
  `load_operating_income.py`, `extract_revenue.py`, `load_revenue.py`,
  `load_stock_prices.py`, `load_13f.py`).
- Editing old migrations, or fixing root revision 596cdf2cfdf4.
- Adding companies, or loading FY2018 or FY2026.
- Ranking 13F managers by total portfolio value.
- Adjusted (non-GAAP) or company-defined FCF.
- Any price vendor other than Yahoo.
- Notebooks.

## 3. Environment

Python 3.10+ with uv. SQLAlchemy 2, psycopg 3, pymongo 4, python-dotenv.
Secrets in `src/stock_db/alembic_migration/.env`. PostgreSQL schemas `dev` and
`final`. MongoDB database `stock_intelligence`. Alembic head 9eb117ff2a64.

## 4. Interface contract

- `dev.quarterly_operating_cash_flow`: ticker, period_start, period_end,
  `operating_cash_flow_usd` bigint (signed), `source_facts` jsonb not null.
  Primary key (ticker, period_start, period_end), foreign key to
  `dev.quarterly_revenue`.
- `final.company_financials_quarterly` gains `operating_cash_flow_usd` and
  `free_cash_flow_usd` as its last columns. The first 12 columns stay identical.
- `dev.quarterly_valuation_inputs`, same key: diluted EPS and method, split
  factor, shares outstanding and its date, total debt, cash, source_facts.
- `data/reference/stock_splits.csv`: ticker, ex_date, ratio, source_url.
- `final.valuation_quarterly` (140 rows): price_date, close, market_cap_usd,
  ttm_eps, pe, ev_usd, ttm_revenue_usd, ev_to_revenue, ttm_fcf_usd,
  fcf_yield_pct, valuation_status.
- `final.valuation_annual`: the quarterly view at fiscal Q4 (35 rows).
- MongoDB `earnings_releases`: one document per Exhibit 99.1 (ticker,
  source_url, sha256, fetched_at, body).
- `dev.quarterly_product_kpis`: ticker, period, kpi, value (nullable), unit,
  source_url not null, source_text, definition_note. A row must have a value or
  a note. Served by `final.product_kpis_quarterly`.
- New reader `sec_companyfacts.mongo_unit_concepts(ticker, taxonomy, tags,
  unit)`. Existing functions unchanged.

## 5. Behaviour

- Operating cash flow: `NetCashProvidedByUsedInOperatingActivities`, year to
  date from the original 10-Q or 10-K. Q1 as reported, Q2 to Q4 by subtraction,
  sign kept. Missing input or same-day conflict stops the load.
- FCF = operating cash flow minus capex_usd, in SQL. NULL if either is missing.
- Split basis: everything on today's share basis, using the sourced splits
  file. Ex-dates from memory, not checked: NVDA 2021-07-20 4:1 and 2024-06-10
  10:1, AMZN 2022-06-06 20:1, GOOGL 2022-07-18 20:1.
- P/E: `close` on the last trading day on or before period end, divided by TTM
  diluted EPS (sum of four quarters; Q4 = annual minus nine months). NULL with
  status "eps <= 0" when TTM EPS is not positive.
- Market cap: close times cover-page shares outstanding (all share classes
  summed for GOOGL and META). Fail loudly if Company Facts lacks the total.
- EV = market cap + total debt (no leases, no double counting) minus cash and
  cash equivalents, at period end. TTM revenue from `dev.quarterly_revenue`.
- FCF yield = 100 times TTM FCF divided by market cap. Negative values kept.
- Valuation is at period end with originally filed values. No disclosure-date
  variant.
- Product KPIs: inspect MongoDB first. If no collection holds sourced quarterly
  segment values, store each Exhibit 99.1 in `earnings_releases`; a reviewed
  CSV supplies each value and its quoted sentence, and the loader fails if the
  sentence is not in the stored body. A definition change gets a note; values
  are never joined across a definition change.

## 6. Constraints

Due Dec 7. Shared RDS, add only; new revisions chain from 9eb117ff2a64.
SEC User-Agent and at least 0.2 s between requests. One transaction and one
advisory lock per loader run. Reruns change nothing. Check database size
before loading more 13F ZIPs.

## 7. Acceptance criteria (expected values written before running)

1. All tests pass (3 existing plus new).
2. `alembic heads` shows one head.
3. 140 operating cash flow rows (5 companies x 7 years x 4 quarters).
4. For all 35 company-years, four quarters minus the 10-K annual = 0.
5. MSFT FY2025 Q4: capex 17,079,000,000; revenue 76,441,000,000; margin 44.90;
   FCF = Q4 operating cash flow minus 17,079,000,000. Q4 operating cash flow
   about 42.6 billion from memory (not checked); the binding value is a manual
   trace of the 10-K and the Q3 10-Q.
6. First 12 columns of `final.company_financials_quarterly` unchanged, still
   140 rows.
7. A second identical run changes no stored value.
8. Prices: same day count for all 5 tickers, first day 2019-01-02, still 250
   days per ticker for July 2024 to June 2025; NVDA close ratio across
   2024-06-07 to 2024-06-10 between 0.8 and 1.25.
9. At least 4 distinct 13F report dates; 3 adjacent pairs compared.
10. `final.valuation_quarterly` 140 rows, 125 with TTM EPS; annual 35 rows.
    Sanity bands (not checked): AMZN FY2022 P/E NULL (loss year); MSFT FY2025
    P/E 25 to 45; NVDA FY2025 P/E 30 to 70.
11. Split guard: split-adjusted EPS equals the latest restated comparative
    within 0.01 USD; changing one ratio in a test makes it fail.
12. Every product value has a source URL and its quoted text is found in the
    stored release. Every NULL has a note.
13. No em or en dashes in new lines.

## 8. Open questions (user decides)

1. 13F direction: earlier report dates (2024-09-30, 2024-12-31) or later
   ones (2025-09-30 onward)?
2. Share count for market cap: cover page (default), balance sheet, or diluted
   weighted average?
3. Add a valuation variant priced on the filing date?
4. Q4 EPS: annual minus nine months (default) or a reviewed release CSV?
5. Debt with or without lease liabilities? Cash with or without marketable
   securities?
6. Product sources beyond Exhibit 99.1 (10-Q text, NVDA CFO commentary, META
   slides) allowed?
7. FCF columns appended to the existing view (default) or a new view?
8. Who applies migrations to the shared RDS, and how are revisions
   coordinated?
9. FCF uses gross CapEx (Amazon gross purchases). Label it as different from
   company-reported FCF?

## Plan

Build order, one PR per step:

1. Read only: `alembic current`; save the column snapshot and counts.
2. Prototype operating cash flow for MSFT FY2025; trace Q4 by hand; write the
   expected value in the run log before loading.
3. Operating cash flow migration, loader, tests; run twice (criteria 3 to 7).
4. Prices from 2019-01-01 (criterion 8).
5. Inspect EPS, share and debt tags per ticker; write the splits file.
6. Valuation migration, loader, tests, trip the split guard (10, 11).
7. Inspect MongoDB; apply the decision rule for product KPIs.
8. Product KPI migration, fetcher, loader, tests (12).
9. Two more 13F windows (9).
10. README section per step; dash check.

New files: `load_operating_cash_flow.py`, `load_valuation_inputs.py`,
`fetch_earnings_releases.py`, `load_product_kpis.py`, three migrations, three
test files, `stock_splits.csv`, `product_kpi_releases.csv`. Modified:
`fiscal_metrics.py` (allowed metrics), `sec_companyfacts.py` (one new
function), `README.md`.

Cannot predict: operating cash flow coverage for every period; whether
multi-class share counts exist without dimensions; Yahoo completeness back to
2019; RDS storage headroom; how many product slots end NULL; parallel Alembic
revisions by teammates.
