"""Alembic setup for the users database. Run from the repo root:

    alembic -c backend/users/alembic.ini upgrade head
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.users import models  # noqa: F401  (imports the tables so Base.metadata knows them)
from backend.users.config import get_settings
from backend.users.database import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# The database URL comes from USERS_DATABASE_URL, the same setting the API uses.
# "%" is doubled because Alembic's config treats a single "%" as a placeholder.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

# What --autogenerate compares the database against.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql`: print the SQL instead of running it."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # compare_type: also notice changed column types, e.g. String(100) -> String(200).
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()