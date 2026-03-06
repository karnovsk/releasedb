"""
Alembic environment configuration for ReleaseDB.

This project does not use SQLAlchemy ORM models — migrations are written as raw
SQL executed via op.execute().  Both online and offline modes are supported.

DATABASE_URL environment variable overrides the sqlalchemy.url in alembic.ini.
Example:
    export DATABASE_URL=postgresql+psycopg2://user:pass@localhost/releasedb
    alembic upgrade head
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to alembic.ini values
# ---------------------------------------------------------------------------
config = context.config

# Honour DATABASE_URL env var so credentials never need to live in alembic.ini
database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# Configure Python logging from the ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No metadata target — we write all DDL by hand in each migration
target_metadata = None


# ---------------------------------------------------------------------------
# Offline mode — generates SQL script without a live DB connection
# Run with: alembic upgrade head --sql
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to the database and applies migrations
# Run with: alembic upgrade head
# ---------------------------------------------------------------------------
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
