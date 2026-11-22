"""Preserve Yahoo price observations and expose one clean row per trading day."""

from alembic import op
import sqlalchemy as sa


revision = "a4fb65a18c29"
down_revision = "21d38a56f917"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_price_downloads",
        sa.Column("snapshot_id", sa.Text(), primary_key=True),
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        schema="dev",
    )
    op.create_table(
        "raw_stock_prices",
        sa.Column("snapshot_id", sa.Text(), sa.ForeignKey("dev.stock_price_downloads.snapshot_id")),
        sa.Column("source_row", sa.Integer()),
        sa.Column("raw_timestamp", sa.Text()),
        sa.Column("trade_date", sa.Date()),
        *(sa.Column(name, sa.Text()) for name in
          ("open", "high", "low", "close", "adj_close", "volume", "quality_issue")),
        sa.PrimaryKeyConstraint("snapshot_id", "source_row"),
        schema="dev",
    )
    op.execute("""
        CREATE VIEW dev.stock_prices_daily AS
        SELECT DISTINCT ON (d.ticker, p.trade_date)
            d.ticker, p.trade_date,
            p.open::numeric AS open, p.high::numeric AS high, p.low::numeric AS low,
            p.close::numeric AS close, p.adj_close::numeric AS adj_close,
            p.volume::bigint AS volume, p.snapshot_id, p.source_row
        FROM dev.raw_stock_prices p
        JOIN dev.stock_price_downloads d USING (snapshot_id)
        WHERE p.quality_issue IS NULL
        ORDER BY d.ticker, p.trade_date, d.last_seen DESC, p.snapshot_id, p.source_row
    """)


def downgrade():
    op.execute("DROP VIEW dev.stock_prices_daily")
    op.drop_table("raw_stock_prices", schema="dev")
    op.drop_table("stock_price_downloads", schema="dev")
