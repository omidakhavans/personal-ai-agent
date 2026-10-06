"""Alembic environment for the PostgreSQL workflow-state schema."""

from __future__ import annotations

from logging.config import fileConfig
from os import environ

from sqlalchemy import engine_from_config, pool

from alembic import context
from personal_ai_agent.postgres import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    """Require an explicit database location instead of persisting one in source."""
    url = environ.get("PERSONAL_AI_AGENT_DATABASE_URL")
    if not url:
        raise RuntimeError("Set PERSONAL_AI_AGENT_DATABASE_URL before running Alembic.")
    return url


def run_migrations_offline() -> None:
    """Generate SQL without connecting when an operator requests offline mode."""
    context.configure(url=_database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the explicitly configured PostgreSQL database."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
