# Milestone 2 video script

## E1. Where the data came from (about 60 to 75 seconds)

Open these tabs before recording, in this order.

1. SEC Company Facts (API)
   - Full file: https://data.sec.gov/api/xbrl/companyfacts/CIK0000789019.json
   - Easier on screen: https://data.sec.gov/api/xbrl/companyconcept/CIK0000789019/us-gaap/RevenueFromContractWithCustomerExcludingAssessedTax.json
   - Point at: entityName, then one fact with val, start, end, form, filed.
2. SEC earnings releases (EDGAR)
   - Microsoft 8-K list: https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000789019&type=8-K&dateb=&owner=include&count=40
   - Stored release (Amazon Q4 2025): https://www.sec.gov/Archives/edgar/data/1018724/000101872426000002/amzn-20251231xex991.htm
   - Point at: "AWS segment sales increased 24% year-over-year to $35.6 billion".
3. Yahoo Finance prices (API)
   - https://query1.finance.yahoo.com/v8/finance/chart/MSFT?range=5d&interval=1d
   - Point at: timestamp, and the open, high, low, close, volume arrays.
4. SEC Form 13F data sets
   - https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets
   - Point at: the ZIP list, for example 01sep2025-30nov2025_form13f.zip.

Narration:

"We use four public data sources from two providers. First, the SEC Company
Facts API. It returns every number a company tags in its quarterly and annual
filings, as nested JSON. Here is Microsoft's revenue, with the dates, the form
type and the filing date for each value.

Second, SEC earnings releases. These are the press releases companies file
every quarter on form 8-K. This is Amazon's Q4 2025 release. It has product
numbers that Company Facts does not have, like AWS sales of 35.6 billion
dollars.

Third, Yahoo Finance's chart API for daily stock prices: open, high, low, close
and volume for each trading day.

Fourth, the SEC Form 13F data sets. Each ZIP file holds the stock holdings that
large investment funds report every quarter. We load four of these files.

All four are free and public, and our scripts download them directly with no
manual steps."

Tips: zoom the browser to about 125%; use pretty-print for JSON; do not show
the .env file or any password screen.
