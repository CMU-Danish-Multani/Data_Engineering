"""Keep the SEC input facts behind each reported or derived quarterly revenue."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "21d38a56f917"
down_revision = "bf349cd61e75"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quarterly_revenue", sa.Column("source_facts", JSONB()), schema="dev")


def downgrade() -> None:
    op.drop_column("quarterly_revenue", "source_facts", schema="dev")
