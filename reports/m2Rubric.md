# Milestone 2 rubric (transcribed)

Source: Canvas course 95-815, file `95-815_M2_Rubric_Template.xlsx`
(file 15226940, updated 2026-11-20), read from the Canvas preview on
2026-11-23. Wording kept as in the sheet. Total 40 points.

## Part A: Updated proposal (2)

- A1 (2). Report includes the Milestone 1 content (context, problem statement,
  three or more questions, value), updated where questions changed or M1
  feedback called for it. (1 if copied unchanged despite feedback, or parts
  missing)

## Part B: Data sources (12)

- B1 (3). At least three distinct datasets that provide complementary
  information, ideally from different providers. (2 if three but two largely
  overlap, e.g. the same data split by year or file; 1 if only one or two
  meaningful datasets)
- B2 (2). At least one semi-structured or unstructured dataset (e.g. JSON or
  XML from an API, text, images). (1 if labeled semi-structured but really flat
  tabular data, e.g. a CSV re-saved as JSON)
- B3 (3). Each dataset described: what it contains, where it comes from (with
  link), size (rows, documents or MB), structure and format (can be shown
  visually in video). (2 if one dataset is missing details; 1 if most details
  are missing)
- B4 (2). Each dataset tied to the specific questions it helps answer; every
  dataset contributes. (1 if relevance is stated only in general terms, or one
  dataset has no clear role)
- B5 (2). Real-world data with enough volume and potentially inherent
  messiness kept. (1 if real but trivial: tiny, and/or pre-cleaned or
  transformed before ingestion)

## Part C: Ingestion and storage (12)

- C1 (3). All structured (tabular) datasets ingested into PostgreSQL. (2 if
  some are loaded and others remain only as files; 1 if described or planned
  but not shown loaded)
- C2 (2). Raw tables preserve source records as they are, with no constraints
  or cleaning rules at the raw stage that discard records. (1 if constraints or
  cleaning at ingest may silently drop records)
- C3 (2). Semi-structured or unstructured data stored in a suitable system:
  MongoDB, S3 or other object storage, or a shared cloud folder the whole team
  can reach. (1 if stored but a poor fit, or only on one person's laptop)
- C4 (3). Each storage choice justified by the data's shape and how it will be
  used. (2 if justified for some datasets only; 1 if generic, e.g.
  "PostgreSQL is popular")
- C5 (2). Raw data kept separate from cleaned data (separate tables, schemas or
  collections, named so the layer is clear). (1 if separation is unclear or
  some raw data was overwritten)

## Part D: Data quality and initial cleaning (8)

- D1 (3). For each dataset, specific quality issues found, with evidence
  (counts, examples, checks run). (2 if issues are listed without evidence or
  one dataset is skipped; 1 if generic, e.g. "the data was mostly clean") If a
  certain dataset is deemed clean, show evidence, test, and/or justifications.
  This can be demonstrated in the video.
- D2 (3). Data types, missing values and duplicates handled, each with a
  stated decision and reason. (2 if handled but decisions not explained; 1 if
  only one of the three is addressed) This can be demonstrated in the video.
- D3 (2). A log of quality issues and how each was handled, telling critical
  issues (should fail clearly) apart from recoverable ones. (1 if the log is
  incomplete or makes no critical vs recoverable distinction) This can be
  demonstrated in the video.

## Part E: Video (6, 1 point each; 0 of 6 if the teaching team cannot open it)

- E1. Shows where the data came from (source website or API)
- E2. Shows examples of the data and its contents
- E3. Shows how the data was ingested (code or process running)
- E4. Shows where the ingested data is stored (PostgreSQL tables, MongoDB, S3
  or similar)
- E5. Shows the data quality issues
- E6. Shows the data after initial cleaning

## Deductions

- Report not submitted as a PDF: minus 1.
