"""
Shared pytest fixtures for all test modules.

Sets DATABASE_URL to in-memory SQLite before any app module is imported,
then wires up a TestClient with the DB dependency overridden so every test
uses a clean, isolated schema.
"""
import os

# Must be set before any app module is imported.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from database import Base, get_db
import main as app_module

_TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)
Base.metadata.create_all(bind=_TEST_ENGINE)


def _override_get_db():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


app_module.app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(scope="session")
def client():
    # No context manager → startup/shutdown events do NOT fire.
    # We seed the schema manually via Base.metadata.create_all above.
    return TestClient(app_module.app, raise_server_exceptions=True)


@pytest.fixture(scope="session")
def db_session():
    db = _TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def admin_token():
    from auth import create_token
    return create_token("admin", "admin", mfa_verified=False)


@pytest.fixture(scope="session")
def nurse_token():
    from auth import create_token
    return create_token("nurse", "nurse", mfa_verified=False)


@pytest.fixture(scope="session")
def physician_token():
    from auth import create_token
    return create_token("physician", "physician", mfa_verified=False)


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def nurse_headers(nurse_token):
    return {"Authorization": f"Bearer {nurse_token}"}


@pytest.fixture(scope="session")
def physician_headers(physician_token):
    return {"Authorization": f"Bearer {physician_token}"}
