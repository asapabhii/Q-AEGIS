"""Alembic environment.

The connection string comes from ``DATABASE_URL`` via :mod:`app.config`, never
from ``alembic.ini``, so there is one source of truth for where the database is
and no credential in committed config.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.db.base import Base
from app.db.session import require_database_url

# Importing the models package registers every table on Base.metadata. Without
# this import autogenerate sees an empty schema and cheerfully proposes dropping
# all twelve tables.
import app.db.models  # noqa: F401  (imported for its registration side effect)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Return the connection string, failing loudly if it is unset."""
    return require_database_url()


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it, for review before applying."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render the type of every altered column, so a generated migration is
        # explicit rather than relying on the database's current state.
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations against a live connection."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()

    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
