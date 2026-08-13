"""Alembic migrations environment configuration for Nexus-UGC."""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override DB URL from env var if set
db_url = os.getenv("DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Import all models so Alembic can detect them for autogenerate
import backend.app.models.account  # noqa: F401
import backend.app.models.api_key  # noqa: F401
import backend.app.models.campaign  # noqa: F401
import backend.app.models.feature_suggestion  # noqa: F401
import backend.app.models.invite_key  # noqa: F401
import backend.app.models.job  # noqa: F401
import backend.app.models.oauth_state  # noqa: F401
import backend.app.models.persona  # noqa: F401
import backend.app.models.publish_history  # noqa: F401
import backend.app.models.rate_limit  # noqa: F401
import backend.app.models.template  # noqa: F401
import backend.app.models.thumbnail  # noqa: F401
import backend.app.models.user  # noqa: F401
import backend.app.models.webhook_event  # noqa: F401
import backend.app.models.whop  # noqa: F401
from backend.app.core.database import Base

target_metadata = Base.metadata


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


def run_migrations_online() -> None:
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
