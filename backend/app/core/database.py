"""Database engine and session management.

Default: SQLite for local dev. Set DATABASE_URL env for PostgreSQL in production.
"""

import logging
import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

logger = logging.getLogger("nexus.db")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{settings.UPLOAD_DIR}/nexus.db",
)

_is_postgres = DATABASE_URL.startswith("postgresql")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_table(engine, table_name, model_module, model_name):
    """Create table if it doesn't exist."""
    try:
        tables = inspect(engine).get_table_names()
        if table_name not in tables:
            mod = __import__(model_module, fromlist=[model_name])
            cls = getattr(mod, model_name)
            cls.__table__.create(engine)
            logger.info("Created table: %s", table_name)
    except Exception as e:
        logger.warning("Could not create table %s: %s", table_name, e)


def _ensure_column(engine, table, column, col_type="VARCHAR DEFAULT ''"):
    """Add column if it doesn't exist. Handles both SQLite and PostgreSQL."""
    try:
        cols = [c["name"] for c in inspect(engine).get_columns(table)]
        if column not in cols:
            sql = _build_alter_sql(table, column, col_type)
            with engine.connect() as conn:
                conn.execute(text(sql))
                conn.commit()
            logger.info("Added column %s to %s", column, table)
    except Exception as e:
        logger.warning("Could not add column %s to %s: %s", column, table, e)


def _build_alter_sql(table: str, column: str, col_type: str) -> str:
    """Build ALTER TABLE ADD COLUMN SQL compatible with both SQLite and PG."""
    if _is_postgres:
        col_type = _pg_col_type(col_type)
    return f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"


def _pg_col_type(col_type: str) -> str:
    """Translate SQLite-centric col type to Postgres-compatible."""
    replacements = {
        "BOOLEAN DEFAULT 0": "BOOLEAN DEFAULT false",
        "BOOLEAN DEFAULT 1": "BOOLEAN DEFAULT true",
    }
    return replacements.get(col_type, col_type)


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Run schema migrations for columns that may not exist yet."""
    try:
        _ensure_column(engine, "users", "whop_customer_id")
        _ensure_column(engine, "users", "whop_license_key")
        _ensure_column(engine, "users", "google_id")
        _ensure_column(engine, "users", "password_salt")
        _ensure_column(engine, "users", "tenant_id", "VARCHAR DEFAULT NULL")
        _ensure_column(engine, "users", "is_admin", "BOOLEAN DEFAULT 0")

        _ensure_column(engine, "jobs", "aspect_ratio", "VARCHAR DEFAULT 'vertical_9_16'")
        _ensure_column(engine, "jobs", "target_language", "VARCHAR DEFAULT 'en'")

        for col in (
            "twitter_user_id",
            "twitter_access_token_enc",
            "facebook_page_id",
            "facebook_access_token_enc",
            "linkedin_user_id",
            "linkedin_access_token_enc",
        ):
            _ensure_column(engine, "social_accounts", col)

        _ensure_table(engine, "thumbnails", "..models.thumbnail", "Thumbnail")
        _ensure_table(engine, "personas", "..models.persona", "Persona")
        _ensure_table(engine, "posts", "..models.persona", "Post")
        _ensure_table(engine, "schedules", "..models.persona", "Schedule")
        _ensure_table(engine, "campaigns", "..models.campaign", "Campaign")
        _ensure_table(engine, "whop_licenses", "..models.whop", "WhopLicense")
        _ensure_table(engine, "whop_events", "..models.whop", "WhopEvent")
        _ensure_table(engine, "invite_keys", "..models.invite_key", "InviteKey")
        _ensure_table(engine, "tenants", "..models.user", "Tenant")
        _ensure_table(engine, "rate_limit_entries", "..models.rate_limit", "RateLimitEntry")
    except Exception as e:
        logger.error("Migration runner failed: %s", e)
