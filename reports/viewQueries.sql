-- Queries to look at the final views. Run in pgAdmin: database stock_intelligence -> Tools -> Query Tool.
-- Select one query and press F5 (or the play button) to run only that query.

-- 0. List every view in the final schema
SELECT table_name FROM information_schema.views WHERE table_schema = 'final' ORDER BY 1;

-- 1. Financial KPIs (1 to 7): one row per company per quarter
SELECT ticker, fiscal_year, fiscal_quarter, period_end,
       round(revenue_usd / 1e9, 2)              AS revenue_bn,
       round(revenue_growth_yoy_pct, 1)         AS revenue_growth_pct,
       round(capex_usd / 1e9, 2)                AS capex_bn,
       round(capex_growth_yoy_pct, 1)           AS capex_growth_pct,
       round(capex_pct_of_revenue, 1)           AS capex_pct_revenue,
       round(operating_margin_pct, 1)           AS operating_margin_pct,
       round(free_cash_flow_usd / 1e9, 2)       AS free_cash_flow_bn
FROM final.company_financials_quarterly
ORDER BY ticker, fiscal_year, fiscal_quarter;

-- 2. Financial KPIs for one year, all companies side by side (change the year)
SELECT ticker,
       round(sum(revenue_usd) / 1e9, 1)        AS revenue_bn,
       round(sum(capex_usd) / 1e9, 1)          AS capex_bn,
       round(sum(free_cash_flow_usd) / 1e9, 1) AS free_cash_flow_bn,
       round(100.0 * sum(operating_income_usd) / sum(revenue_usd), 1) AS operating_margin_pct
FROM final.company_financials_quarterly
WHERE fiscal_year = 2025
GROUP BY ticker ORDER BY ticker;

-- 3. Valuation KPIs (8 to 10), yearly
SELECT ticker, fiscal_year, price_date, round(close, 2) AS close,
       round(market_cap_usd / 1e12, 2) AS market_cap_trillion,
       round(pe_ratio, 1)              AS pe,
       round(ev_to_revenue, 2)         AS ev_to_revenue,
       round(fcf_yield_pct, 2)         AS fcf_yield_pct,
       valuation_status
FROM final.valuation_annual
ORDER BY fiscal_year, ticker;

-- 4. Valuation KPIs, every quarter (trailing twelve months)
SELECT ticker, fiscal_year, fiscal_quarter, price_date,
       round(pe_ratio, 1) AS pe, round(ev_to_revenue, 2) AS ev_to_revenue,
       round(fcf_yield_pct, 2) AS fcf_yield_pct, valuation_status
FROM final.valuation_quarterly
ORDER BY ticker, period_end;

-- 5. Product KPIs (11 to 13) for the latest quarter of each company's FY2025
SELECT ticker, kpi,
       CASE WHEN unit = 'USD' THEN round(value / 1e9, 2) ELSE round(value, 1) END AS value_bn_or_pct,
       unit, round(yoy_growth_pct, 1) AS growth_pct, definition_note
FROM final.product_kpis_quarterly
WHERE fiscal_year = 2025 AND fiscal_quarter = 4
ORDER BY ticker, kpi;

-- 6. One product KPI over time, with its source link (change the kpi name)
SELECT ticker, fiscal_year, fiscal_quarter, round(value / 1e9, 2) AS value_bn,
       round(yoy_growth_pct, 1) AS growth_pct, source_url
FROM final.product_kpis_quarterly
WHERE kpi = 'aws_revenue_usd'
ORDER BY period_end;

-- 7. Fund holdings: biggest share increases in Microsoft between Sep 30 and Dec 31, 2025
SELECT manager_name, previous_shares, reported_shares, change_in_reported_shares
FROM dev.f13_quarterly_changes
WHERE report_date = DATE '2025-12-31' AND security_ticker = 'MSFT'
  AND comparison_status = 'reported in both quarters'
ORDER BY change_in_reported_shares DESC
LIMIT 20;

-- 8. Daily prices (clean view)
SELECT ticker, count(*) AS days, min(trade_date) AS first_day, max(trade_date) AS last_day
FROM dev.stock_prices_daily GROUP BY ticker ORDER BY ticker;

-- 9. Row counts of all final views (quick health check)
SELECT 'company_financials_quarterly' AS view, count(*) FROM final.company_financials_quarterly
UNION ALL SELECT 'financial_metrics_quarterly', count(*) FROM final.financial_metrics_quarterly
UNION ALL SELECT 'capital_expenditure_quarterly', count(*) FROM final.capital_expenditure_quarterly
UNION ALL SELECT 'valuation_quarterly', count(*) FROM final.valuation_quarterly
UNION ALL SELECT 'valuation_annual', count(*) FROM final.valuation_annual
UNION ALL SELECT 'product_kpis_quarterly', count(*) FROM final.product_kpis_quarterly;
