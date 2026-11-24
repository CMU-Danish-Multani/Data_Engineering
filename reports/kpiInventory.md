# KPI and table inventory (2026-11-23)

Every count below comes from `reports/pipelineCheck_2026-11-23.txt`, produced
by the read-only script `reports/pipelineCheck.py`. Rerun it to refresh.
Database revision: `9c4b2f61e8a7`. Companies: MSFT, GOOGL, AMZN, META, NVDA.
Fiscal years FY2019 to FY2025 (28 quarters per company).

## Flow

```
SEC Company Facts API -> MongoDB companyfacts_concepts -> dev.quarterly_* tables -> final views
Yahoo Finance chart API -> dev.raw_stock_prices -> dev.stock_prices_daily ----------^
SEC 8-K Exhibit 99.1   -> MongoDB earnings_releases -> dev.quarterly_product_kpis -> final.product_kpis_quarterly
SEC Form 13F ZIPs      -> dev.f13_* raw tables -> dev.f13_* review and comparison views
```

## The 13 KPIs per company

| # | KPI | Source | Stored in | Served by |
|---|---|---|---|---|
| 1 | Revenue | SEC Company Facts (10-Q, 10-K) | dev.quarterly_revenue | final.company_financials_quarterly |
| 2 | Revenue growth YoY | derived | (view) | final.company_financials_quarterly |
| 3 | Capital expenditure | SEC Company Facts | dev.quarterly_capex | final.company_financials_quarterly |
| 4 | CapEx growth YoY | derived | (view) | final.company_financials_quarterly |
| 5 | CapEx share of revenue | derived | (view) | final.company_financials_quarterly |
| 6 | Operating margin | SEC Company Facts (operating income) | dev.quarterly_operating_income | final.company_financials_quarterly |
| 7 | Free cash flow | SEC Company Facts (operating cash flow) minus CapEx | dev.quarterly_operating_cash_flow | final.company_financials_quarterly |
| 8 | P/E | SEC EPS + Yahoo close | dev.quarterly_valuation_inputs, dev.stock_prices_daily | final.valuation_quarterly, final.valuation_annual |
| 9 | EV/Revenue | SEC shares, debt, cash, revenue + Yahoo close | same | same |
| 10 | FCF yield | free cash flow + market cap | same | same |
| 11 to 13 | Product KPIs (3 per company, below) | SEC 8-K earnings releases | MongoDB earnings_releases, dev.quarterly_product_kpis | final.product_kpis_quarterly |

Product KPIs (`kpi` column of `final.product_kpis_quarterly`):

| Company | KPI 11 | KPI 12 | KPI 13 |
|---|---|---|---|
| AMZN | aws_revenue_usd | its yoy_growth_pct | aws_operating_margin_pct |
| GOOGL | google_cloud_revenue_usd | its yoy_growth_pct | google_cloud_operating_margin_pct |
| MSFT | microsoft_cloud_revenue_usd | azure_revenue_growth_pct | microsoft_cloud_gross_margin_pct |
| META | family_of_apps_revenue_usd | advertising_revenue_usd growth | average_revenue_per_person_usd (not in releases, all NULL) |
| NVDA | data_center_revenue_usd | its yoy_growth_pct | data_center_share_of_revenue_pct |

Institutional holdings (research question 2, not a numbered KPI): SEC Form 13F,
four report dates 2025-03-31 to 2025-12-31, served by `dev.f13_quarterly_changes`.

## Coverage and known gaps

See the coverage lines in `reports/pipelineCheck_2026-11-23.txt`. Gaps are NULL
with a reason, never estimated:

- Growth KPIs start in FY2020 (FY2019 is the baseline).
- Valuation needs four quarters, so each company's first three quarters are
  NULL; five quarters ending in 2018 have no price. AMZN FY2022 P/E is NULL
  because trailing EPS was negative.
- Google Cloud revenue begins Q4 2019; its operating income begins Q4 2020.
- Meta Family of Apps begins Q4 2021; Meta does not publish revenue per person
  in its release.
- Microsoft Cloud revenue is stated in 21 releases, gross margin in 3.
- NVIDIA Data Center revenue is not in the FY2020 releases (it was in the CFO
  commentary exhibit).
- Free cash flow uses gross CapEx, so it differs from Amazon's own definition.
