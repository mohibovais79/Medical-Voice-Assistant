"""Alembic environment configuration.

Reads the DB connection string from our app settings (DATABASE_URL env var)
and uses SQLModel's metadata for autogenerate support.
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Import our app config + SQLModel metadata so autogenerate can detect models
from app.core.config import get_settings
from app.db.schema import Patient  # noqa: F401 — registers the table
import sqlmodel

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use SQLModel's metadata (shared with SQLAlchemy) for autogenerate
target_metadata = sqlmodel.SQLModel.metadata

# Inject the database URL from our app settings
settings = get_settings()
if settings.database_url:
    url = settings.database_url
    if url.startswith("postgresql://") and "+" not in url.split("://")[0]:
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    config.set_main_option("sqlalchemy.url", url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emits SQL without a live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (uses a real DB connection)."""
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
