"""Preserve SEC 13F downloads and expose as-filed holdings for the tracked issuers."""

import sqlalchemy as sa
from alembic import op


revision = "617c2d32e9ba"
down_revision = "a4fb65a18c29"
branch_labels = None
depends_on = None


def raw_table(name, columns):
    op.create_table(
        name,
        sa.Column("download_id", sa.Integer(), sa.ForeignKey("dev.f13_downloads.id")),
        sa.Column("source_row", sa.Integer()),
        *(sa.Column(col, sa.Text()) for col in columns.split()),
        sa.PrimaryKeyConstraint("download_id", "source_row"),
        schema="dev",
    )
    op.create_index(f"ix_{name}_filing", name, ["download_id", "accession_number"], schema="dev")


def upgrade():
    op.create_table(
        "f13_downloads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_url", sa.Text(), nullable=False, unique=True),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("archive_zip", sa.LargeBinary(), nullable=False),
        sa.Column("loaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("info_rows_scanned", sa.Integer()),
        sa.Column("info_rows_matched", sa.Integer()),
        schema="dev",
    )
    securities = op.create_table(
        "f13_securities",
        sa.Column("cusip", sa.Text(), primary_key=True),
        sa.Column("ticker", sa.Text(), sa.ForeignKey("dev.companies.ticker"), nullable=False),
        sa.Column("security_ticker", sa.Text(), nullable=False),
        schema="dev",
    )
    op.bulk_insert(securities, [
        {"cusip": cusip, "ticker": issuer, "security_ticker": security}
        for cusip, issuer, security in [
            ("594918104", "MSFT", "MSFT"), ("023135106", "AMZN", "AMZN"),
            ("30303M102", "META", "META"), ("67066G104", "NVDA", "NVDA"),
            ("02079K305", "GOOGL", "GOOGL"), ("02079K107", "GOOGL", "GOOG"),
        ]
    ])
    raw_table("f13_submission", "accession_number filing_date submissiontype cik periodofreport")
    raw_table("f13_coverpage", "accession_number reportcalendarorquarter isamendment amendmentno amendmenttype filingmanager_name reporttype")
    raw_table("f13_infotable", "accession_number infotable_sk nameofissuer titleofclass cusip figi value sshprnamt sshprnamttype putcall investmentdiscretion othermanager voting_auth_sole voting_auth_shared voting_auth_none")
    op.execute("""
        CREATE VIEW dev.f13_holdings_as_filed AS
        SELECT i.download_id, i.source_row, i.accession_number, s.cik AS manager_cik,
               c.filingmanager_name AS manager_name,
               CASE WHEN pg_input_is_valid(s.periodofreport, 'date') THEN s.periodofreport::date END AS report_date,
               CASE WHEN pg_input_is_valid(s.filing_date, 'date') THEN s.filing_date::date END AS filed_on,
               s.submissiontype AS form_type, c.amendmenttype AS amendment_type,
               m.ticker, m.security_ticker, i.cusip, i.titleofclass AS security_class,
               NULLIF(trim(i.putcall), '') AS put_call, i.sshprnamttype AS quantity_type,
               CASE WHEN trim(i.sshprnamt) ~ '^[0-9]+$' THEN i.sshprnamt::numeric END AS reported_quantity,
               CASE WHEN trim(i.value) ~ '^[0-9]+$' THEN i.value::numeric END AS reported_value_usd
        FROM dev.f13_infotable i
        JOIN dev.f13_securities m ON m.cusip = upper(trim(i.cusip))
        LEFT JOIN dev.f13_submission s USING (download_id, accession_number)
        LEFT JOIN dev.f13_coverpage c USING (download_id, accession_number)
    """)


def downgrade():
    op.execute("DROP VIEW dev.f13_holdings_as_filed")
    for table in ("f13_infotable", "f13_coverpage", "f13_submission", "f13_securities", "f13_downloads"):
        op.drop_table(table, schema="dev")
