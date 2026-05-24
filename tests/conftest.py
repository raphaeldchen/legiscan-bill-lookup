import os
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://localhost/bill_tracker_test")
os.environ.setdefault("LEGISCAN_API_KEY", "test_key")

import database

@pytest.fixture(scope="session", autouse=True)
def setup_schema():
    database.init_pool()
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            with open("migrations/001_initial.sql") as f:
                cur.execute(f.read())
    yield

@pytest.fixture(autouse=True)
def clean_tables():
    yield
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE users, sessions, bills, categories, fetch_jobs RESTART IDENTITY CASCADE"
            )

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app, raise_server_exceptions=True)

@pytest.fixture
def auth_client(client):
    """Returns (client, user_dict) with an active session cookie."""
    r = client.post("/api/auth/signup", json={"email": "intern@test.com", "password": "password123"})
    assert r.status_code == 200
    return client, r.json()
