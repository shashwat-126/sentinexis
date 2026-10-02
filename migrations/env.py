"""
Alembic environment for the AIOps platform's shared Postgres database.

Design note: each service (incident-service, notification-service, etc.)
still calls `Base.metadata.create_all()` on startup for local/dev
convenience -- that's unchanged and still works out of the box with
`docker compose up`. Alembic is the production migration path: run
`alembic upgrade head` once against a fresh database and then rely on
versioned migrations (not create_all) for every schema change from then
on. Because services live in independent directories (several with
hyphenated names that aren't importable as plain Python packages), this
env.py defines the target schema directly with SQLAlchemy Core `Table`
objects in the baseline revision rather than importing each service's
ORM models -- one source of truth for migrations, decoupled from any
single service's internal module layout.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/aiops")
config.set_main_option("sqlalchemy.url", DATABASE_URL)

target_metadata = None  # baseline revision defines tables explicitly; see versions/


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
