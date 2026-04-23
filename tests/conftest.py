"""
tests/conftest.py

Shared pytest fixtures.

Two test modes:
  1. Tests using `client` fixture → in-memory SQLite DB (fast, no Neon needed)
  2. Tests tagged @pytest.mark.real_db → hit the real TEST_DATABASE_URL
     Set TEST_DATABASE_URL in your .env (or environment) before running.
"""

import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load .env so DATABASE_URL is set before importing src modules
from dotenv import load_dotenv
load_dotenv()

from src.database import Base, get_db
from src.main import app


# ── In-memory SQLite fixture (no network needed) ─────────────────────────────
SQLITE_URL = "sqlite:///./test_temp.db"

@pytest.fixture(scope="session")
def sqlite_engine():
    engine = create_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    try:
        if os.path.exists("test_temp.db"):
            os.remove("test_temp.db")
    except PermissionError:
        pass


@pytest.fixture(scope="function")
def client(sqlite_engine):
    """TestClient backed by a fresh SQLite session for each test."""
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Real-DB fixture (hits TEST_DATABASE_URL) ──────────────────────────────────
@pytest.fixture(scope="module")
def real_client():
    """TestClient backed by the real PostgreSQL test database."""
    test_db_url = os.environ.get("TEST_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not test_db_url:
        pytest.skip("No TEST_DATABASE_URL configured – skipping real-DB tests")

    real_engine = create_engine(test_db_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=real_engine)
    RealSession = sessionmaker(autocommit=False, autoflush=False, bind=real_engine)

    def override_get_db():
        db = RealSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    real_engine.dispose()
