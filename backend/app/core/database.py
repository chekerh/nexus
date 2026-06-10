"""Database engine and session management.

Default: SQLite for local dev. Set DATABASE_URL env for PostgreSQL in production.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{settings.UPLOAD_DIR}/nexus.db",
)

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


def init_db():
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Run schema migrations for columns that may not exist yet."""
    try:
        from sqlalchemy import inspect
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("jobs")]
        if "aspect_ratio" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE jobs ADD COLUMN aspect_ratio VARCHAR DEFAULT 'vertical_9_16'"
                    )
                )
                conn.commit()
        if "target_language" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE jobs ADD COLUMN target_language VARCHAR DEFAULT 'en'"
                    )
                )
                conn.commit()
    except Exception:
        pass
