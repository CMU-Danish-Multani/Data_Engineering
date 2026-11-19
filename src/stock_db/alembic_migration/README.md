# Database migrations

All Alembic configuration and revision scripts live in this folder. Backend
code and tests have separate sibling folders. Models and table migrations are
intentionally deferred until schema planning is complete.

## Environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
from the repository root:

```sh
uv sync --locked --python 3.12
source .venv/bin/activate
```

The local environment uses Python 3.12. There is no `.python-version` pin;
the project permits Python 3.10 or newer. Other supported versions can be
selected with `--python`. Only Python 3.12 has been checked for this setup.
Commit `pyproject.toml` and `uv.lock`; `.venv` and `.env` files are ignored.
Dependencies are managed in `pyproject.toml`; the existing empty
`requirements.txt` is retained, but is not used by uv.

## Commands

Run these from the repository root with the environment activated:

```sh
# Inspect history without a database connection.
alembic -c src/stock_db/alembic_migration/alembic.ini history

# Create an empty revision when ready to define a schema change.
alembic -c src/stock_db/alembic_migration/alembic.ini revision -m "describe change"
```

Add your database details to `src/stock_db/alembic_migration/.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://username:password@localhost:5432/stock_db
```

Alembic automatically loads this file when running its migration environment,
regardless of the working directory. Existing shell environment variables take
precedence. The `.env` file is ignored by Git, so teammates must create their
own copy using the format above. Use
`postgresql+psycopg://` to select the installed driver, and URL-encode special
characters in credentials.

```sh
# Preview SQL without connecting to PostgreSQL.
alembic -c src/stock_db/alembic_migration/alembic.ini upgrade head --sql

# Apply revisions to the configured database.
alembic -c src/stock_db/alembic_migration/alembic.ini upgrade head

# Show the database's current revision.
alembic -c src/stock_db/alembic_migration/alembic.ini current
```

You can also run `alembic` directly from this directory, where it will discover
`alembic.ini` automatically. Paths inside the configuration are relative to
the configuration file rather than the working directory.

## After model planning

Import the shared SQLAlchemy base and model modules in `env.py`, then assign
`target_metadata = Base.metadata`. With a database available, create a candidate
migration using `revision --autogenerate -m "describe change"`. Review both
`upgrade()` and `downgrade()` before applying it, and commit the revision script.
Autogeneration is unavailable while metadata is unset.

Alembic versions the database schema, not the history of individual stock data
records. Historical data storage will be part of the later table design.
