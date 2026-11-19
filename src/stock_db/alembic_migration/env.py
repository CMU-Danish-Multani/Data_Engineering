"""Alembic environment; model metadata will be connected after schema design."""

import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

load_dotenv(Path(__file__).resolve().with_name(".env"), override=False)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Replace with the shared SQLAlchemy Base.metadata once models are defined.
# Import all models here as well so their tables are registered in metadata.
target_metadata = None


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "Set DATABASE_URL before running database migrations. "
            "Set it in alembic_migration/.env or export it in your shell."
        )
    return url


def run_migrations_offline() -> None:
    """Generate SQL without connecting to the database."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations using the configured database connection."""
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
