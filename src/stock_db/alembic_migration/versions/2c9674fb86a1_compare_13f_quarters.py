"""Reconcile 13F filings and compare reported shares in adjacent quarters."""

from alembic import op


revision = "2c9674fb86a1"
down_revision = "617c2d32e9ba"
branch_labels = None
depends_on = None


def upgrade():
    # Start from filing metadata: a restatement can remove every tracked holding.
    op.execute("""
        CREATE OR REPLACE VIEW dev.f13_filing_review AS
        WITH filing AS (
            SELECT s.download_id, s.accession_number,
                   CASE WHEN trim(s.cik) ~ '^[0-9]{1,10}$'
                        THEN lpad(trim(s.cik), 10, '0') END AS manager_cik,
                   c.filingmanager_name AS manager_name,
                   CASE WHEN pg_input_is_valid(s.periodofreport, 'date')
                        THEN s.periodofreport::date END AS report_date,
                   CASE WHEN pg_input_is_valid(s.filing_date, 'date')
                        THEN s.filing_date::date END AS filed_on,
                   CASE WHEN s.submissiontype = '13F-HR'
                             AND c.amendmenttype = '' AND c.isamendment IN ('', 'N')
                             AND c.amendmentno IN ('', '0') THEN 'original'
                        WHEN s.submissiontype = '13F-HR/A' AND c.isamendment = 'Y'
                             AND c.amendmenttype = 'RESTATEMENT' THEN 'restatement'
                        WHEN s.submissiontype = '13F-HR/A' AND c.isamendment = 'Y'
                             AND c.amendmenttype = 'NEW HOLDINGS' THEN 'addition'
                        WHEN s.submissiontype IN ('13F-NT', '13F-NT/A') THEN 'notice'
                        ELSE 'unrecognized' END AS kind,
                   CASE WHEN s.submissiontype = '13F-HR' THEN 0
                        WHEN c.amendmentno ~ '^[1-9][0-9]{0,8}$'
                        THEN c.amendmentno::integer END AS seq
            FROM dev.f13_submission s
            LEFT JOIN dev.f13_coverpage c USING (download_id, accession_number)
        ), baseline AS (
            SELECT filing.*,
                   max(seq) FILTER (WHERE kind IN ('original','restatement'))
                       OVER (PARTITION BY manager_cik, report_date) AS base_seq
            FROM filing
        ), checks AS (
            SELECT manager_cik, report_date,
                   bool_or(kind IN ('notice','unrecognized') OR seq IS NULL OR filed_on IS NULL)
                       AS unsupported,
                   count(*) FILTER (WHERE seq >= base_seq) AS n,
                   count(DISTINCT seq) FILTER (WHERE seq >= base_seq) AS unique_n,
                   max(seq) - max(base_seq) + 1 AS expected_n
            FROM baseline GROUP BY manager_cik, report_date
        )
        SELECT b.download_id, b.accession_number, b.manager_cik, b.manager_name,
               b.report_date, b.filed_on, b.kind, b.seq,
               CASE WHEN b.manager_cik !~ '^[0-9]{10}$' OR b.manager_cik IS NULL
                          OR b.report_date IS NULL THEN 'invalid identifier or date'
                    WHEN b.kind = 'notice' THEN 'notice'
                    WHEN k.unsupported THEN 'review filing type or metadata'
                    WHEN b.base_seq IS NULL THEN 'missing original or restatement'
                    WHEN k.n <> k.unique_n OR k.n <> k.expected_n THEN 'ambiguous amendment sequence'
                    WHEN b.seq < b.base_seq THEN 'superseded'
                    ELSE 'use' END AS decision
        FROM baseline b LEFT JOIN checks k USING (manager_cik, report_date)
    """)
    op.execute("""
        CREATE OR REPLACE VIEW dev.f13_manager_positions AS
        WITH effective AS (
            SELECT * FROM dev.f13_filing_review WHERE decision = 'use'
        ), reports AS (
            SELECT manager_cik, report_date, (array_agg(manager_name ORDER BY seq DESC))[1] AS manager_name,
                   array_agg(accession_number ORDER BY seq) AS filing_accessions
            FROM effective GROUP BY manager_cik, report_date
        ), shares AS (
            SELECT f.manager_cik, f.report_date, upper(trim(i.cusip)) AS cusip,
                   count(*) AS line_count,
                   CASE WHEN bool_and(trim(i.sshprnamt) ~ '^[0-9]+$' AND i.sshprnamt IS NOT NULL)
                        THEN sum(CASE WHEN trim(i.sshprnamt) ~ '^[0-9]+$'
                                      THEN i.sshprnamt::numeric END) END AS reported_shares
            FROM effective f JOIN dev.f13_infotable i USING (download_id, accession_number)
            WHERE upper(trim(i.sshprnamttype)) = 'SH' AND nullif(trim(i.putcall), '') IS NULL
            GROUP BY f.manager_cik, f.report_date, upper(trim(i.cusip))
        )
        SELECT r.manager_cik, r.manager_name, r.report_date, m.ticker, m.security_ticker,
               m.cusip, r.filing_accessions, coalesce(s.line_count, 0) AS share_lines, s.reported_shares
        FROM reports r CROSS JOIN dev.f13_securities m
        LEFT JOIN shares s ON (s.manager_cik, s.report_date, s.cusip) = (r.manager_cik, r.report_date, m.cusip)
        WHERE r.report_date = (date_trunc('quarter', r.report_date) + interval '3 months - 1 day')::date
    """)
    op.execute("""
        CREATE OR REPLACE VIEW dev.f13_quarterly_changes AS
        WITH history AS (
            SELECT p.*,
                   lag(report_date) OVER w AS previous_report_date,
                   lag(share_lines) OVER w AS previous_share_lines,
                   lag(reported_shares) OVER w AS previous_shares,
                   lag(filing_accessions) OVER w AS previous_filing_accessions
            FROM dev.f13_manager_positions p
            WINDOW w AS (PARTITION BY manager_cik, cusip ORDER BY report_date)
        )
        SELECT manager_cik, manager_name, ticker, security_ticker, cusip,
               previous_report_date, report_date, previous_shares, reported_shares,
               reported_shares - previous_shares AS change_in_reported_shares,
               CASE WHEN share_lines = 0 THEN 'only reported in prior quarter'
                    WHEN previous_share_lines = 0 THEN 'only reported in current quarter'
                    WHEN previous_shares IS NULL OR reported_shares IS NULL THEN 'invalid quantity'
                    ELSE 'reported in both quarters' END AS comparison_status,
               previous_filing_accessions, filing_accessions
        FROM history
        WHERE previous_report_date = date_trunc('quarter', report_date)::date - 1
          AND (previous_share_lines > 0 OR share_lines > 0)
    """)


def downgrade():
    for name in ("f13_quarterly_changes", "f13_manager_positions", "f13_filing_review"):
        op.execute(f"DROP VIEW dev.{name}")
