"""Alembic env.py — configured for the MiSt user DB (Postgres).

Run from the backend/ directory:
    alembic upgrade head          # apply all migrations
    alembic revision --autogenerate -m "describe change"  # generate new migration
"""

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import all models so their tables are registered with UserBase.metadata.
from app.config import settings
from app.db.user_base import UserBase
from app.models.user import Meal, MealIngredient, User  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

log = logging.getLogger(__name__)

# Override the URL from the app settings so it respects .env / env vars.
config.set_main_option("sqlalchemy.url", settings.user_db_url)

target_metadata = UserBase.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a live DB connection (for review / CI)."""
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
    """Apply migrations against a live DB connection."""
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
