# Milestone 2: rubric check of reports/milestone2Report.pdf

Checked 2026-11-23 against `reports/m2Rubric.md`. Due tonight, 11:59 pm
Eastern. Canvas shows the group submission as not submitted.

Scope: this checks the 5 page `milestone2Report.pdf` in this repository. The
engineering handoff says a separate 4 page version and the demo video are with
Alan and are not in Git. That version has not been read. If it is the one being
submitted, check it against the same list.

## The main problem: the report describes the plan, not what was built

| Topic | What the report says | What is actually built |
|---|---|---|
| Datasets | 9 datasets from 7 providers, plus banks | 3 datasets from 2 providers: SEC Company Facts, Yahoo daily prices, SEC Form 13F |
| Company Facts storage | Amazon S3 | MongoDB Atlas (`companyfacts_concepts`, `companyfacts_snapshots`) |
| Layers | raw, staging, core, serving | `dev` (raw evidence plus processed tables) and `final` (serving views) |
| Quality section | "Expected" issues only | Measured counts exist (see below) |
| Length | 5 pages | Instructions say 3 to 4 |

## Item by item (likely points, my estimate)

- A1 (2). Milestone 1 content present. Likely 2, but the questions mention
  banks, CFPB and transcripts that are no longer in scope.
- B1 (3). Three real datasets exist. Likely 3 only if the report names the 3
  that were built.
- B2 (2). Company Facts is nested JSON from an API. Likely 2.
- B3 (3). Sizes say "measured at first load". Most sizes are missing. Likely 1
  to 2 as written.
- B4 (2). Questions are tied to sources, but some sources listed are not built.
  Likely 1.
- B5 (2). Real, large data. Likely 2.
- C1 (3). Prices and 13F are in PostgreSQL. Needs to be shown loaded.
- C2 (2). Raw price rows are stored as text with a `quality_issue` flag instead
  of being dropped. 13F rows are copied as text. Likely 2 if stated.
- C3 (2). MongoDB is a good fit, but the report says S3. Likely 1 as written.
- C4 (3). Justification is written for S3 and banking stores. Likely 1 to 2.
- C5 (2). Raw and cleaned are separate tables, but both sit in schema `dev`.
  Name them clearly (for example `dev.raw_stock_prices` -> `dev.stock_prices_daily`
  -> `final.*`). Likely 1 to 2.
- D1 (3). Only expected issues, no evidence. Likely 1 as written.
- D2 (3). Types, missing values, duplicates are handled in code but not
  explained in the report. Likely 1 to 2.
- D3 (2). No log shown. Likely 0 to 1 as written.
- E1 to E6 (6). Depends on the video. Zero if any instructor or TA cannot open
  it.

## Evidence that already exists and can go into the report

These numbers are from the engineering handoff dated 2026-11-22 (single
snapshot). They have not been rechecked against the live databases today.

- Prices: 2,250 raw observations in 9 saved histories, 0 flagged, 1,250 clean
  ticker-days, 250 per company, July 2024 to June 2025.
- 13F: 6,800,308 holdings lines scanned across two filing windows, 102,780 kept
  for the 6 tracked share classes. 272 superseded filings and 6 ambiguous
  amendment sequences, each with an explicit decision in `dev.f13_filing_review`.
- Company Facts: 5 snapshots, 2,819 concept documents (AMZN 556, GOOGL 564,
  META 477, MSFT 578, NVDA 644).
- Revenue: 140 quarters, FY2019 to FY2025. Example reconciliation: Amazon FY2019
  Q4 is 87.437 billion in the earnings release and 87.436 billion by
  subtraction; the 1 million difference is stored in `source_facts`.
- Critical vs recoverable (for D3): critical issues stop the load with an error
  (conflicting same-date values, missing cumulative inputs, differences above
  1 million USD). Recoverable issues are kept and flagged (`quality_issue` on
  price rows, `decision` in the 13F review view).

## Smallest set of fixes for tonight

1. Replace the 9-dataset table with the 3 built datasets: link, size, format,
   where stored, why stored there.
2. Change S3 to MongoDB for Company Facts. Remove staging, core and banking.
3. Replace "Expected data quality issues" with the measured counts above.
4. Add a short quality log table: issue, count, critical or recoverable, action.
5. Cut to 4 pages. Put the video link and its access settings in the PDF.

## Check of reports/team8Milestone2Report.pdf (simple version, 2026-11-23)

This replaces the assessment above for the new report. Each line names where
the rubric item is met. Points are not predicted.

- A1 (2). Page 1: problem, three questions, value ("Who benefits"),
  motivation, and an "Updates since Milestone 1" box. Met.
- B1 (3). Page 2 Table 1: four distinct datasets from two providers (SEC and
  Yahoo), each with a different role. Met.
- B2 (2). Table 1: nested JSON (semi-structured) and HTML text (unstructured).
  Met.
- B3 (3). Table 1: contents, link, size (documents, rows, MB), format. Met.
- B4 (2). Page 1 question table names the datasets for each question; all
  four datasets are used. Met.
- B5 (2). Page 2: sizes, "13,540,608 13F rows scanned", messiness kept. Met.
- C1 (3). Table 1: both structured datasets (prices, 13F) are in PostgreSQL.
  Shown loaded in the video. Met if the video shows it.
- C2 (2). Page 2 raw bullet: no keys or type rules, rows flagged, never
  deleted. Met.
- C3 (2). Page 2: MongoDB Atlas and AWS RDS, shared cloud services. Met.
- C4 (3). Table 1 last column: shape and use for each dataset. Met.
- C5 (2). Page 2: raw, clean (dev) and final layers with table names. Met.
- D1 (3). Page 3 Table 3: issues with counts for all four datasets; prices
  shown clean with evidence (0 of 12,170 flagged). Met.
- D2 (3). Page 3: types, missing values and duplicates, each with a decision
  and reason. Met.
- D3 (2). Page 3 Table 3: log with Critical vs Recoverable. Met.
- E1 to E6 (6). Page 4 lists what the video shows. NOT MET YET: the video link
  is a placeholder; 0 of 6 if the teaching team cannot open it.
- Deduction (PDF). Report is a PDF. Met.
- Instructions: 3 to 4 pages (4); team number, members, project manager and
  meeting notes link on page 1. Met.
