"""Test configuration — SQLite temp file, test client, auth fixtures."""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use a temp file for test DB to avoid in-memory isolation issues
_fd, _test_db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)

os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["JWT_SECRET"] = "test-secret-do-not-use-in-production"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["CSRF_ENABLED"] = "false"
os.environ["DYNAMIC_MODEL_SELECTION"] = "false"
os.environ["WHISPER_BINARY_PATH"] = "/dev/null"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="nexus-test-")

from backend.app.core.database import Base, get_db, init_db
from backend.app.main import app
from backend.app.models.user import SubscriptionTier, User

# Initialize the app's database with tables
init_db()

# Test session factory using the same DB URL
from sqlalchemy import create_engine as _ce
from sqlalchemy.orm import sessionmaker as _sm

engine = _ce(f"sqlite:///{_test_db_path}", connect_args={"check_same_thread": False})
TestingSessionLocal = _sm(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def clean_db():
    """Clear all rows between tests (keep schema)."""
    for table in reversed(Base.metadata.sorted_tables):
        db = TestingSessionLocal()
        try:
            db.execute(table.delete())
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_user(db):
    """Create a test user and return (user, password)."""
    from backend.app.core.middleware import hash_password

    password = "testpass123"
    pw_hash, pw_salt = hash_password(password)
    user = User(
        id="test-user-id",
        email="test@example.com",
        display_name="Test User",
        password_hash=pw_hash,
        password_salt=pw_salt,
        subscription_tier=SubscriptionTier.FREE,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, password


@pytest.fixture
def user_token(client, test_user):
    """Get a valid JWT for the test user."""
    user, password = test_user
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": user.email,
            "password": password,
        },
    )
    assert resp.status_code == 200
    return resp.json()["token"]


@pytest.fixture
def auth_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


import atexit
import contextlib


@atexit.register
def _cleanup():
    with contextlib.suppress(Exception):
        os.unlink(_test_db_path)
