"""
tests/conftest.py
~~~~~~~~~~~~~~~~~
Integration test fixtures for the ReleaseDB API.

Prerequisites
-------------
1. Start Postgres (both databases are created automatically):

       docker compose up -d

2. Install dependencies from the project root:

       pip install -r api/requirements.txt
       pip install -e "sdk/.[dev]"
       pip install -r api/tests/requirements.txt

3. Run migrations against the test database:

       (done automatically by the _run_migrations session fixture)

Run the tests:

    pytest api/tests/ -v

Override the database URL:

    TEST_DATABASE_URL=postgresql://user:pass@host/releasedb_test pytest api/tests/
"""

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest

# ---------------------------------------------------------------------------
# Database connection strings.
# DATABASE_URL must be set BEFORE api.main is imported so asyncpg picks it up.
# ---------------------------------------------------------------------------
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://releasedb:releasedb@localhost:5432/releasedb_test",
)
TEST_TOKEN = "testtoken"

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["RELEASEDB_API_TOKEN"] = TEST_TOKEN

_API_DIR = Path(__file__).parent.parent

# ---------------------------------------------------------------------------
# Session fixture: run Alembic migrations once per test session.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _run_migrations():
    """Apply all schema migrations to the test database."""
    # Alembic uses SQLAlchemy which needs the +psycopg2 dialect prefix.
    alembic_url = TEST_DB_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "migrations/alembic.ini", "upgrade", "head"],
        cwd=_API_DIR,
        env={**os.environ, "DATABASE_URL": alembic_url},
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migration failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Session fixture: create the HTTP test client (triggers the FastAPI lifespan).
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client(_run_migrations):
    """FastAPI test client with the auth header pre-set."""
    from api.main import app
    from fastapi.testclient import TestClient

    with TestClient(app, raise_server_exceptions=True) as c:
        c.headers["Authorization"] = f"Bearer {TEST_TOKEN}"
        yield c


# ---------------------------------------------------------------------------
# Function fixture: truncate all tables before every test.
# ---------------------------------------------------------------------------

# Listed in an order that respects FK constraints (children before parents),
# but CASCADE handles any missed dependencies automatically.
_ALL_TABLES = [
    "release_events",
    "validation_results",
    "validation_runs",
    "release_field_values",
    "deployments",
    "approvals",
    "artifacts",
    "release_dependencies",
    "releases",
    "validation_definitions",
    "release_type_field_defs",
    "release_type_configs",
    "projects",
    "environments",
    "teams",
]


@pytest.fixture(autouse=True)
def _clean_db():
    """Truncate all data tables so each test starts with a clean database."""
    conn = psycopg2.connect(TEST_DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"TRUNCATE {', '.join(_ALL_TABLES)} RESTART IDENTITY CASCADE")
    cur.close()
    conn.close()
