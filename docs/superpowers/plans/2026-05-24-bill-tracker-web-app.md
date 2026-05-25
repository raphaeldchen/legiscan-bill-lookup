# Bill Tracker Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `criminaljustice.py` into a multi-user FastAPI web app where interns log in, manage keyword categories, fetch IL bills from LegiScan into a shared PostgreSQL cache, and filter/export results.

**Architecture:** FastAPI serves both a JSON API (`/api/*`) and a plain HTML+JS frontend (catch-all returns `index.html`). PostgreSQL stores users, sessions, per-user categories, shared bills, and fetch job progress. Bill fetching runs as a FastAPI `BackgroundTask`; the frontend polls for status.

**Tech Stack:** Python 3.11+, FastAPI, psycopg2-binary, bcrypt, python-dotenv, requests, pytest, httpx

---

## File Map

| File | Responsibility |
|---|---|
| `migrations/001_initial.sql` | Create all five tables |
| `database.py` | psycopg2 ThreadedConnectionPool; `get_conn()` context manager |
| `auth.py` | bcrypt helpers, session token generation, `get_current_user()` dependency |
| `models.py` | Pydantic request/response schemas |
| `routers/auth.py` | `/api/auth/*` — signup, login, logout, me |
| `routers/categories.py` | `/api/categories/*` — CRUD |
| `routers/fetch.py` | `/api/fetch` — start job, status, latest |
| `routers/bills.py` | `/api/bills` — list, filter, export CSV |
| `services/legiscan.py` | `fetch_master_list()`, `sync_bills()` — ported from `criminaljustice.py` |
| `services/filter.py` | `filter_bills()` — keyword SQL query |
| `main.py` | FastAPI app assembly, static files, catch-all |
| `static/index.html` | Single HTML shell |
| `static/style.css` | App styles |
| `static/app.js` | Client-side routing + all page renders + API calls |
| `tests/conftest.py` | pytest fixtures: DB setup, table truncation, TestClient, auth_client |
| `tests/test_auth_core.py` | Unit tests for bcrypt + token helpers |
| `tests/test_auth_endpoints.py` | Integration tests for auth routes |
| `tests/test_categories.py` | Integration tests for categories CRUD |
| `tests/test_legiscan.py` | Unit tests for legiscan service (mocked HTTP) |
| `tests/test_fetch.py` | Integration tests for fetch endpoints |
| `tests/test_bills.py` | Integration tests for bills list/filter/export |
| `requirements.txt` | Pinned dependencies |
| `.env.example` | Example env vars |
| `render.yaml` | Render deploy config |
| `Procfile` | `uvicorn` start command |

---

## Task 1: Project Bootstrap

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `pytest.ini`
- Create directory skeletons: `migrations/`, `routers/`, `services/`, `static/`, `tests/`

- [ ] **Step 1: Write `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
psycopg2-binary==2.9.9
bcrypt==4.2.1
python-dotenv==1.0.1
requests==2.32.3
pytest==8.3.2
httpx==0.27.2
```

- [ ] **Step 2: Write `.env.example`**

```
DATABASE_URL=postgresql://localhost/bill_tracker
LEGISCAN_API_KEY=your_key_here
```

- [ ] **Step 3: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 4: Create directory skeleton**

```bash
mkdir -p migrations routers services static tests
touch routers/__init__.py services/__init__.py tests/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 6: Create the test database**

```bash
createdb bill_tracker_test
```

- [ ] **Step 7: Commit**

```bash
git init
git add requirements.txt .env.example pytest.ini
git commit -m "chore: project bootstrap"
```

---

## Task 2: Database Layer

**Files:**
- Create: `migrations/001_initial.sql`
- Create: `database.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `migrations/001_initial.sql`**

```sql
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS bills (
    bill_id          TEXT PRIMARY KEY,
    number           TEXT,
    title            TEXT,
    description      TEXT,
    status           TEXT,
    chamber          TEXT,
    committee        TEXT,
    sponsors         TEXT,
    last_action      TEXT,
    last_action_date TEXT,
    raw_json         JSONB,
    fetched_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS categories (
    id         SERIAL PRIMARY KEY,
    user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    keywords   TEXT[] DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS fetch_jobs (
    id            SERIAL PRIMARY KEY,
    status        TEXT DEFAULT 'queued',
    started_at    TIMESTAMPTZ,
    finished_at   TIMESTAMPTZ,
    total_bills   INTEGER,
    bills_fetched INTEGER DEFAULT 0,
    bills_updated INTEGER DEFAULT 0,
    error_msg     TEXT
);
```

- [ ] **Step 2: Write `database.py`**

```python
import os
import psycopg2
import psycopg2.pool
from contextlib import contextmanager

_pool = None

def init_pool():
    global _pool
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=os.environ["DATABASE_URL"],
    )

@contextmanager
def get_conn():
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
```

- [ ] **Step 3: Write a minimal `main.py` so conftest can import it**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
```

- [ ] **Step 4: Write `tests/conftest.py`**

```python
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
```

- [ ] **Step 5: Verify the test runner can collect (no errors)**

```bash
pytest tests/ --co -q
```

Expected: `no tests ran` with no import errors.

- [ ] **Step 6: Commit**

```bash
git add database.py migrations/ tests/conftest.py main.py
git commit -m "feat: database layer and schema migration"
```

---

## Task 3: Auth Core

**Files:**
- Create: `auth.py`
- Create: `tests/test_auth_core.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_core.py`:

```python
from auth import hash_password, verify_password, generate_token

def test_password_round_trip():
    pw = "correct-horse-battery"
    assert verify_password(pw, hash_password(pw))

def test_wrong_password_fails():
    assert not verify_password("wrong", hash_password("right"))

def test_generate_token_is_unique():
    assert generate_token() != generate_token()

def test_generate_token_is_64_chars():
    # 32 bytes as hex = 64 characters
    assert len(generate_token()) == 64
```

- [ ] **Step 2: Run tests — expect ImportError**

```bash
pytest tests/test_auth_core.py -v
```

Expected: `ImportError: cannot import name 'hash_password' from 'auth'`

- [ ] **Step 3: Write `auth.py`**

```python
import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
import database

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def generate_token() -> str:
    return secrets.token_hex(32)

def create_session(user_id: int) -> str:
    token = generate_token()
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (user_id, token, expires_at) VALUES (%s, %s, %s)",
                (user_id, token, expires),
            )
    return token

def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.email FROM users u
                   JOIN sessions s ON s.user_id = u.id
                   WHERE s.token = %s AND s.expires_at > now()""",
                (token,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": row[0], "email": row[1]}
```

- [ ] **Step 4: Run tests — expect 4 passed**

```bash
pytest tests/test_auth_core.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add auth.py tests/test_auth_core.py
git commit -m "feat: auth core — bcrypt, session tokens"
```

---

## Task 4: Auth Endpoints

**Files:**
- Create: `models.py`
- Create: `routers/auth.py`
- Create: `tests/test_auth_endpoints.py`
- Modify: `main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_auth_endpoints.py`:

```python
def test_signup(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "a@b.com"
    assert "id" in data
    assert "session" in r.cookies

def test_signup_duplicate_email(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw"})
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw"})
    assert r.status_code == 400

def test_login(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw123"})
    assert r.status_code == 200
    assert "session" in r.cookies

def test_login_wrong_password(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401

def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401

def test_me_returns_user(auth_client):
    client, user = auth_client
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "intern@test.com"

def test_logout_clears_session(auth_client):
    client, _ = auth_client
    client.post("/api/auth/logout")
    r = client.get("/api/auth/me")
    assert r.status_code == 401
```

- [ ] **Step 2: Run — expect 404s**

```bash
pytest tests/test_auth_endpoints.py -v
```

Expected: all fail (routes don't exist yet).

- [ ] **Step 3: Write `models.py`**

```python
from pydantic import BaseModel
from typing import Optional, List

class SignupRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class CategoryCreate(BaseModel):
    name: str
    keywords: List[str] = []

class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    keywords: Optional[List[str]] = None

class FilterRequest(BaseModel):
    category_ids: List[int]
```

- [ ] **Step 4: Write `routers/auth.py`**

```python
from fastapi import APIRouter, Response, HTTPException, Depends, Request
from models import SignupRequest, LoginRequest
from auth import hash_password, verify_password, create_session, get_current_user
import database

router = APIRouter(prefix="/api/auth")

@router.post("/signup")
def signup(req: SignupRequest, response: Response):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (req.email,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            pw_hash = hash_password(req.password)
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
                (req.email, pw_hash),
            )
            row = cur.fetchone()
    user_id, email = row
    token = create_session(user_id)
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=30 * 24 * 3600
    )
    return {"id": user_id, "email": email}

@router.post("/login")
def login(req: LoginRequest, response: Response):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash FROM users WHERE email = %s", (req.email,)
            )
            row = cur.fetchone()
    if not row or not verify_password(req.password, row[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(row[0])
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=30 * 24 * 3600
    )
    return {"id": row[0], "email": row[1]}

@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
    response.delete_cookie("session")
    return {"ok": True}

@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
```

- [ ] **Step 5: Update `main.py` to include auth router**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database
from routers import auth as auth_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router.router)
```

- [ ] **Step 6: Run — expect 7 passed**

```bash
pytest tests/test_auth_endpoints.py -v
```

Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add models.py routers/auth.py tests/test_auth_endpoints.py main.py
git commit -m "feat: auth endpoints — signup, login, logout, me"
```

---

## Task 5: Categories CRUD

**Files:**
- Create: `routers/categories.py`
- Create: `tests/test_categories.py`
- Modify: `main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_categories.py`:

```python
def test_create_category(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "Criminal Justice", "keywords": ["felony", "police"]})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Criminal Justice"
    assert "felony" in data["keywords"]
    assert "id" in data

def test_list_categories(auth_client):
    client, _ = auth_client
    client.post("/api/categories", json={"name": "Cat A", "keywords": ["foo"]})
    client.post("/api/categories", json={"name": "Cat B", "keywords": ["bar"]})
    r = client.get("/api/categories")
    assert r.status_code == 200
    assert len(r.json()) == 2

def test_update_category_name(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "Old Name", "keywords": ["a"]})
    cat_id = r.json()["id"]
    r = client.put(f"/api/categories/{cat_id}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"
    assert r.json()["keywords"] == ["a"]   # keywords unchanged

def test_update_category_keywords(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "Cat", "keywords": ["old"]})
    cat_id = r.json()["id"]
    r = client.put(f"/api/categories/{cat_id}", json={"keywords": ["new1", "new2"]})
    assert r.status_code == 200
    assert r.json()["keywords"] == ["new1", "new2"]

def test_delete_category(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "To Delete", "keywords": []})
    cat_id = r.json()["id"]
    client.delete(f"/api/categories/{cat_id}")
    assert len(client.get("/api/categories").json()) == 0

def test_categories_isolated_per_user(client):
    client.post("/api/auth/signup", json={"email": "u1@test.com", "password": "pw"})
    client.post("/api/categories", json={"name": "U1 Cat", "keywords": []})
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "u2@test.com", "password": "pw"})
    assert len(client.get("/api/categories").json()) == 0

def test_delete_other_users_category_returns_404(client):
    client.post("/api/auth/signup", json={"email": "u1@test.com", "password": "pw"})
    r = client.post("/api/categories", json={"name": "U1 Cat", "keywords": []})
    cat_id = r.json()["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "u2@test.com", "password": "pw"})
    assert client.delete(f"/api/categories/{cat_id}").status_code == 404
```

- [ ] **Step 2: Run — expect 404s**

```bash
pytest tests/test_categories.py -v
```

Expected: all fail.

- [ ] **Step 3: Write `routers/categories.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from models import CategoryCreate, CategoryUpdate
from auth import get_current_user
import database

router = APIRouter(prefix="/api/categories")

@router.get("")
def list_categories(user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, keywords FROM categories WHERE user_id = %s ORDER BY created_at",
                (user["id"],),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "name": r[1], "keywords": r[2]} for r in rows]

@router.post("")
def create_category(req: CategoryCreate, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO categories (user_id, name, keywords) VALUES (%s, %s, %s) "
                "RETURNING id, name, keywords",
                (user["id"], req.name, req.keywords),
            )
            row = cur.fetchone()
    return {"id": row[0], "name": row[1], "keywords": row[2]}

@router.put("/{category_id}")
def update_category(category_id: int, req: CategoryUpdate, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categories WHERE id = %s AND user_id = %s",
                (category_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")

            set_parts = ["updated_at = now()"]
            values = []
            if req.name is not None:
                set_parts.append("name = %s")
                values.append(req.name)
            if req.keywords is not None:
                set_parts.append("keywords = %s")
                values.append(req.keywords)
            values.append(category_id)

            cur.execute(
                f"UPDATE categories SET {', '.join(set_parts)} WHERE id = %s "
                "RETURNING id, name, keywords",
                values,
            )
            row = cur.fetchone()
    return {"id": row[0], "name": row[1], "keywords": row[2]}

@router.delete("/{category_id}")
def delete_category(category_id: int, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM categories WHERE id = %s AND user_id = %s RETURNING id",
                (category_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")
    return {"ok": True}
```

- [ ] **Step 4: Add categories router to `main.py`**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database
from routers import auth as auth_router
from routers import categories as categories_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(categories_router.router)
```

- [ ] **Step 5: Run — expect 7 passed**

```bash
pytest tests/test_categories.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add routers/categories.py tests/test_categories.py main.py models.py
git commit -m "feat: categories CRUD endpoints"
```

---

## Task 6: LegiScan Service

**Files:**
- Create: `services/legiscan.py`
- Create: `tests/test_legiscan.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_legiscan.py`:

```python
from unittest.mock import patch, MagicMock
import pytest
from services.legiscan import fetch_master_list, _extract_committee, _fetch_bill

def _mock_response(payload):
    m = MagicMock()
    m.json.return_value = payload
    m.raise_for_status = MagicMock()
    return m

def test_extract_committee_found():
    history = [{"action": "First reading"}, {"action": "Referred to Judiciary Committee"}]
    assert _extract_committee(history) == "Judiciary Committee"

def test_extract_committee_uses_most_recent():
    history = [
        {"action": "Referred to Agriculture Committee"},
        {"action": "Re-referred to Judiciary Committee"},
    ]
    assert _extract_committee(history) == "Judiciary Committee"

def test_extract_committee_none():
    assert _extract_committee([]) is None
    assert _extract_committee([{"action": "passed"}]) is None

def test_fetch_master_list_returns_stubs():
    payload = {
        "masterlist": {
            "session": {"session_id": 1},
            "1": {"bill_id": 1, "number": "HB 100", "last_action_date": "2025-01-01"},
            "2": {"bill_id": 2, "number": "SB 200", "last_action_date": "2025-01-02"},
        }
    }
    with patch("services.legiscan.requests.get", return_value=_mock_response(payload)):
        stubs = fetch_master_list()
    assert len(stubs) == 2
    assert stubs[0]["number"] == "HB 100"

def test_fetch_master_list_raises_on_missing_key():
    with patch("services.legiscan.requests.get", return_value=_mock_response({"status": "ERROR"})):
        with pytest.raises(ValueError, match="No masterlist"):
            fetch_master_list()

def test_fetch_bill_returns_none_on_missing_key():
    with patch("services.legiscan.requests.get", return_value=_mock_response({"status": "ERROR"})):
        assert _fetch_bill("999", "testkey", retries=1) is None

def test_fetch_bill_returns_bill_dict():
    payload = {"bill": {"bill_id": 1, "number": "HB 100", "sponsors": [], "history": []}}
    with patch("services.legiscan.requests.get", return_value=_mock_response(payload)):
        result = _fetch_bill("1", "testkey", retries=1)
    assert result["number"] == "HB 100"
```

- [ ] **Step 2: Run — expect ImportError**

```bash
pytest tests/test_legiscan.py -v
```

Expected: `ImportError: cannot import name 'fetch_master_list' from 'services.legiscan'`

- [ ] **Step 3: Write `services/legiscan.py`**

```python
import json
import logging
import os
import re
import time
from typing import Optional

import requests

import database

logger = logging.getLogger(__name__)
BASE_URL = "https://api.legiscan.com/"


def _get_api_key() -> str:
    return os.environ["LEGISCAN_API_KEY"]


def fetch_master_list() -> list:
    """Call LegiScan getMasterList for IL; return list of bill stubs."""
    resp = requests.get(
        BASE_URL, params={"key": _get_api_key(), "op": "getMasterList", "state": "IL"}
    )
    resp.raise_for_status()
    data = resp.json()
    if "masterlist" not in data:
        raise ValueError("No masterlist in LegiScan response")
    return list(data["masterlist"].values())[1:]  # skip session metadata dict


def _extract_committee(history: list) -> Optional[str]:
    """Scan history in reverse; return most recent committee name or None."""
    patterns = [
        r"referred to (.+?) committee",
        r"assigned to (.+?) committee",
        r"to (.+?) committee",
    ]
    for event in reversed(history):
        action = event.get("action", "").lower()
        for pattern in patterns:
            match = re.search(pattern, action)
            if match:
                return match.group(1).strip().title() + " Committee"
    return None


def _fetch_bill(bill_id: str, api_key: str, retries: int = 3) -> Optional[dict]:
    """Fetch one bill from LegiScan; returns bill dict or None on failure."""
    for attempt in range(retries):
        try:
            resp = requests.get(
                BASE_URL, params={"key": api_key, "op": "getBill", "id": bill_id}
            )
            data = resp.json()
            if "bill" not in data:
                return None
            return data["bill"]
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(3)
            else:
                logger.error(f"Failed bill {bill_id} after {retries} attempts: {e}")
    return None


def _update_job_progress(job_id: int, fetched: int, updated: int) -> None:
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fetch_jobs SET bills_fetched=%s, bills_updated=%s WHERE id=%s",
                (fetched, updated, job_id),
            )


def sync_bills(stubs: list, job_id: int) -> None:
    """
    Upsert all bills from stubs into the DB.
    Re-fetches from LegiScan only when last_action_date has changed.
    Updates fetch_jobs progress row as it goes.
    """
    api_key = _get_api_key()
    total = len(stubs)

    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fetch_jobs SET status='running', started_at=now(), total_bills=%s WHERE id=%s",
                (total, job_id),
            )

    fetched = updated = 0

    for stub in stubs:
        bill_id = str(stub.get("bill_id"))
        last_action_date = stub.get("last_action_date", "")

        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_action_date FROM bills WHERE bill_id = %s", (bill_id,)
                )
                cached = cur.fetchone()

        if cached and cached[0] == last_action_date:
            fetched += 1
            _update_job_progress(job_id, fetched, updated)
            continue

        full_bill = _fetch_bill(bill_id, api_key)
        if not full_bill:
            fetched += 1
            _update_job_progress(job_id, fetched, updated)
            continue

        sponsors = "; ".join(
            s["name"]
            for s in full_bill.get("sponsors", [])
            if isinstance(s, dict) and "name" in s
        )
        number = stub.get("number", "")
        if number.startswith("H"):
            chamber = "House"
        elif number.startswith("S"):
            chamber = "Senate"
        else:
            chamber = "Unknown"

        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO bills
                       (bill_id, number, title, description, status, chamber,
                        committee, sponsors, last_action, last_action_date, raw_json, fetched_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
                       ON CONFLICT (bill_id) DO UPDATE SET
                         title=EXCLUDED.title, description=EXCLUDED.description,
                         status=EXCLUDED.status, chamber=EXCLUDED.chamber,
                         committee=EXCLUDED.committee, sponsors=EXCLUDED.sponsors,
                         last_action=EXCLUDED.last_action,
                         last_action_date=EXCLUDED.last_action_date,
                         raw_json=EXCLUDED.raw_json, fetched_at=now()""",
                    (
                        bill_id, number,
                        stub.get("title", ""),
                        stub.get("description", "").replace("\n", " "),
                        str(stub.get("status", "")),
                        chamber,
                        _extract_committee(full_bill.get("history", [])) or "",
                        sponsors,
                        stub.get("last_action", "").replace("\n", " "),
                        last_action_date,
                        json.dumps(full_bill),
                    ),
                )

        fetched += 1
        updated += 1
        _update_job_progress(job_id, fetched, updated)

    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fetch_jobs SET status='done', finished_at=now() WHERE id=%s",
                (job_id,),
            )
```

- [ ] **Step 4: Run — expect 7 passed**

```bash
pytest tests/test_legiscan.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add services/legiscan.py tests/test_legiscan.py
git commit -m "feat: LegiScan service — fetch_master_list, sync_bills"
```

---

## Task 7: Fetch Endpoints

**Files:**
- Create: `routers/fetch.py`
- Create: `tests/test_fetch.py`
- Modify: `main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_fetch.py`:

```python
from unittest.mock import patch

def test_start_fetch_creates_job(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        r = client.post("/api/fetch")
    assert r.status_code == 200
    assert "job_id" in r.json()

def test_start_fetch_no_duplicate_while_queued(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        r1 = client.post("/api/fetch")
        r2 = client.post("/api/fetch")
    assert r1.json()["job_id"] == r2.json()["job_id"]

def test_fetch_status_returns_job(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        r = client.post("/api/fetch")
    job_id = r.json()["job_id"]
    r = client.get(f"/api/fetch/status/{job_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("queued", "running", "done", "failed")
    assert "bills_fetched" in data

def test_fetch_status_404_for_unknown(auth_client):
    client, _ = auth_client
    assert client.get("/api/fetch/status/99999").status_code == 404

def test_fetch_latest_none_when_no_jobs(auth_client):
    client, _ = auth_client
    r = client.get("/api/fetch/latest")
    assert r.status_code == 200
    assert r.json() is None

def test_fetch_latest_returns_most_recent(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        client.post("/api/fetch")
    r = client.get("/api/fetch/latest")
    assert r.json() is not None
    assert "status" in r.json()

def test_fetch_requires_auth(client):
    assert client.post("/api/fetch").status_code == 401
```

- [ ] **Step 2: Run — expect 404s/401s**

```bash
pytest tests/test_fetch.py -v
```

Expected: all fail.

- [ ] **Step 3: Write `routers/fetch.py`**

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from auth import get_current_user
import database
from services.legiscan import fetch_master_list, sync_bills

router = APIRouter(prefix="/api/fetch")


def _run_sync(job_id: int) -> None:
    try:
        stubs = fetch_master_list()
        sync_bills(stubs, job_id)
    except Exception as e:
        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fetch_jobs SET status='failed', finished_at=now(), error_msg=%s WHERE id=%s",
                    (str(e), job_id),
                )


def _row_to_dict(row) -> dict:
    return {
        "id": row[0], "status": row[1], "total_bills": row[2],
        "bills_fetched": row[3], "bills_updated": row[4], "error_msg": row[5],
        "started_at": row[6].isoformat() if row[6] else None,
        "finished_at": row[7].isoformat() if row[7] else None,
    }

_JOB_COLS = "id, status, total_bills, bills_fetched, bills_updated, error_msg, started_at, finished_at"


@router.post("")
def start_fetch(background_tasks: BackgroundTasks, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT {_JOB_COLS} FROM fetch_jobs "
                "WHERE status IN ('queued','running') ORDER BY id DESC LIMIT 1"
            )
            row = cur.fetchone()
    if row:
        return {"job_id": row[0]}

    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO fetch_jobs DEFAULT VALUES RETURNING id")
            job_id = cur.fetchone()[0]

    background_tasks.add_task(_run_sync, job_id)
    return {"job_id": job_id}


@router.get("/latest")
def get_latest(user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_JOB_COLS} FROM fetch_jobs ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
    return _row_to_dict(row) if row else None


@router.get("/status/{job_id}")
def get_status(job_id: int, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(f"SELECT {_JOB_COLS} FROM fetch_jobs WHERE id=%s", (job_id,))
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return _row_to_dict(row)
```

- [ ] **Step 4: Add fetch router to `main.py`**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database
from routers import auth as auth_router
from routers import categories as categories_router
from routers import fetch as fetch_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(categories_router.router)
app.include_router(fetch_router.router)
```

- [ ] **Step 5: Run — expect 7 passed**

```bash
pytest tests/test_fetch.py -v
```

Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add routers/fetch.py tests/test_fetch.py main.py
git commit -m "feat: fetch endpoints — background sync, status polling"
```

---

## Task 8: Bills & Filter Service

**Files:**
- Create: `services/filter.py`
- Create: `routers/bills.py`
- Create: `tests/test_bills.py`
- Modify: `main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bills.py`:

```python
import json
import database

def _insert_bill(bill_id: str, description: str, last_action_date: str = "2025-01-01"):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bills (bill_id, number, title, description, status,
                   chamber, committee, sponsors, last_action, last_action_date, raw_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (bill_id, f"HB {bill_id}", f"Title {bill_id}", description,
                 "1", "House", "", "", "", last_action_date, json.dumps({})),
            )

def test_list_bills_empty(auth_client):
    client, _ = auth_client
    r = client.get("/api/bills")
    assert r.status_code == 200
    assert r.json() == {"bills": [], "total": 0, "page": 1}

def test_list_bills_returns_all(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A bill about felony")
    _insert_bill("2", "A bill about schools")
    assert client.get("/api/bills").json()["total"] == 2

def test_list_bills_pagination(auth_client):
    client, _ = auth_client
    for i in range(5):
        _insert_bill(str(i), f"Bill {i}")
    assert len(client.get("/api/bills?page=1&limit=3").json()["bills"]) == 3
    assert len(client.get("/api/bills?page=2&limit=3").json()["bills"]) == 2

def test_filter_bills_by_keyword(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A bill about felony charges")
    _insert_bill("2", "A bill about school funding")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    cat_id = r.json()["id"]
    data = client.post("/api/bills/filter", json={"category_ids": [cat_id]}).json()
    assert data["total"] == 1
    assert data["bills"][0]["bill_id"] == "1"

def test_filter_case_insensitive(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A bill about FELONY charges")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    cat_id = r.json()["id"]
    assert client.post("/api/bills/filter", json={"category_ids": [cat_id]}).json()["total"] == 1

def test_filter_empty_keywords_returns_empty(auth_client):
    client, _ = auth_client
    _insert_bill("1", "Any bill")
    r = client.post("/api/categories", json={"name": "Empty", "keywords": []})
    cat_id = r.json()["id"]
    assert client.post("/api/bills/filter", json={"category_ids": [cat_id]}).json()["bills"] == []

def test_filter_multiple_categories(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A felony bill")
    _insert_bill("2", "An energy bill")
    _insert_bill("3", "An unrelated bill")
    r1 = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    r2 = client.post("/api/categories", json={"name": "Energy", "keywords": ["energy"]})
    data = client.post("/api/bills/filter", json={"category_ids": [r1.json()["id"], r2.json()["id"]]}).json()
    assert data["total"] == 2

def test_filter_cannot_use_other_users_category(client):
    client.post("/api/auth/signup", json={"email": "u1@test.com", "password": "pw"})
    _insert_bill("1", "A felony bill")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    u1_cat_id = r.json()["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "u2@test.com", "password": "pw"})
    assert client.post("/api/bills/filter", json={"category_ids": [u1_cat_id]}).json()["total"] == 0

def test_export_csv_includes_header(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A felony bill")
    r = client.get("/api/bills/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "bill_id" in r.text
    assert "1" in r.text

def test_bills_require_auth(client):
    assert client.get("/api/bills").status_code == 401
```

- [ ] **Step 2: Run — expect failures**

```bash
pytest tests/test_bills.py -v
```

Expected: all fail.

- [ ] **Step 3: Write `services/filter.py`**

```python
from typing import List
import database


def _bill_row_to_dict(row) -> dict:
    return {
        "bill_id": row[0], "number": row[1], "title": row[2],
        "description": row[3], "status": row[4], "chamber": row[5],
        "committee": row[6], "sponsors": row[7],
        "last_action": row[8], "last_action_date": row[9],
    }


def filter_bills(category_ids: List[int], user_id: int, page: int = 1, limit: int = 50) -> dict:
    """
    Return bills whose description matches any keyword from the given categories.
    Only considers categories owned by user_id — prevents cross-user data access.
    Uses PostgreSQL ILIKE ANY for case-insensitive matching in a single query.
    """
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT keywords FROM categories WHERE id = ANY(%s) AND user_id = %s",
                (category_ids, user_id),
            )
            rows = cur.fetchall()

    keywords = [kw for row in rows for kw in row[0]]
    if not keywords:
        return {"bills": [], "total": 0, "page": page}

    patterns = [f"%{kw}%" for kw in keywords]
    offset = (page - 1) * limit

    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT bill_id, number, title, description, status, chamber,
                   committee, sponsors, last_action, last_action_date
                   FROM bills WHERE description ILIKE ANY(%s)
                   ORDER BY last_action_date DESC LIMIT %s OFFSET %s""",
                (patterns, limit, offset),
            )
            bills = cur.fetchall()
            cur.execute(
                "SELECT COUNT(*) FROM bills WHERE description ILIKE ANY(%s)", (patterns,)
            )
            total = cur.fetchone()[0]

    return {"bills": [_bill_row_to_dict(b) for b in bills], "total": total, "page": page}
```

- [ ] **Step 4: Write `routers/bills.py`**

```python
import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from auth import get_current_user
from models import FilterRequest
from services.filter import filter_bills, _bill_row_to_dict
import database

router = APIRouter(prefix="/api/bills")

_CSV_FIELDS = [
    "bill_id", "number", "title", "description", "status",
    "chamber", "committee", "sponsors", "last_action", "last_action_date",
]


@router.get("")
def list_bills(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    offset = (page - 1) * limit
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT bill_id, number, title, description, status, chamber,
                   committee, sponsors, last_action, last_action_date
                   FROM bills ORDER BY last_action_date DESC LIMIT %s OFFSET %s""",
                (limit, offset),
            )
            bills = cur.fetchall()
            cur.execute("SELECT COUNT(*) FROM bills")
            total = cur.fetchone()[0]
    return {"bills": [_bill_row_to_dict(b) for b in bills], "total": total, "page": page}


@router.post("/filter")
def filter_bills_endpoint(
    req: FilterRequest,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    return filter_bills(req.category_ids, user["id"], page=page, limit=limit)


@router.get("/export")
def export_bills(category_ids: str = Query(""), user=Depends(get_current_user)):
    if category_ids.strip():
        ids = [int(i) for i in category_ids.split(",") if i.strip()]
        bills = filter_bills(ids, user["id"], page=1, limit=100_000)["bills"]
    else:
        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT bill_id, number, title, description, status, chamber,
                       committee, sponsors, last_action, last_action_date
                       FROM bills ORDER BY last_action_date DESC"""
                )
                bills = [_bill_row_to_dict(r) for r in cur.fetchall()]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    writer.writerows(bills)

    return Response(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bills.csv"},
    )
```

- [ ] **Step 5: Add bills router to `main.py`**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from dotenv import load_dotenv
import database
from routers import auth as auth_router
from routers import categories as categories_router
from routers import fetch as fetch_router
from routers import bills as bills_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router.router)
app.include_router(categories_router.router)
app.include_router(fetch_router.router)
app.include_router(bills_router.router)
```

- [ ] **Step 6: Run — expect 10 passed**

```bash
pytest tests/test_bills.py -v
```

Expected: 10 passed.

- [ ] **Step 7: Run full suite**

```bash
pytest -v
```

Expected: all tests pass. Fix any failures before continuing.

- [ ] **Step 8: Commit**

```bash
git add services/filter.py routers/bills.py tests/test_bills.py main.py
git commit -m "feat: bills list, keyword filter, CSV export"
```

---

## Task 9: App Assembly

**Files:**
- Modify: `main.py` (add static files mount and catch-all)
- Create: `static/index.html` (placeholder)

- [ ] **Step 1: Create placeholder `static/index.html`**

```html
<!DOCTYPE html>
<html><body><h1>Bill Tracker</h1></body></html>
```

- [ ] **Step 2: Finalize `main.py`**

```python
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv
import database
from routers import auth as auth_router
from routers import categories as categories_router
from routers import fetch as fetch_router
from routers import bills as bills_router

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    yield

app = FastAPI(lifespan=lifespan)

# API routes first (FastAPI matches in registration order)
app.include_router(auth_router.router)
app.include_router(categories_router.router)
app.include_router(fetch_router.router)
app.include_router(bills_router.router)

# Static assets served at /static/
app.mount("/static", StaticFiles(directory="static"), name="static")

# Catch-all: serve index.html for all non-API paths (client-side routing)
@app.get("/{full_path:path}")
def catch_all(full_path: str):
    return FileResponse("static/index.html")
```

- [ ] **Step 3: Smoke-test the server**

```bash
uvicorn main:app --reload &
sleep 2
curl -s http://localhost:8000/api/auth/me
# expected: {"detail":"Not authenticated"}
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/
# expected: 200
kill %1
```

- [ ] **Step 4: Commit**

```bash
git add main.py static/index.html
git commit -m "feat: app assembly — static files, catch-all routing"
```

---

## Task 10: Frontend Shell

**Files:**
- Create: `static/style.css`
- Modify: `static/index.html`
- Create: `static/app.js`

- [ ] **Step 1: Write `static/style.css`**

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0f1117;
  color: #e2e8f0;
  min-height: 100vh;
}

#nav {
  display: flex;
  align-items: center;
  border-bottom: 1px solid #2d3748;
  padding: 0 24px;
  background: #1a1f2e;
}
#nav a {
  display: block;
  padding: 14px 16px;
  font-size: 14px;
  color: #a0aec0;
  text-decoration: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
}
#nav a.active { color: #e2e8f0; border-bottom-color: #3b82f6; }
#nav .spacer { flex: 1; }
#nav .user-info { font-size: 12px; color: #4a5568; padding: 0 8px; }
#nav .logout-btn {
  background: none; border: none; cursor: pointer;
  font-size: 12px; color: #4a5568; padding: 8px;
}
#nav .logout-btn:hover { color: #e2e8f0; }

#app { padding: 28px; max-width: 1200px; }

.stat-cards { display: flex; gap: 16px; margin-bottom: 24px; }
.stat-card { background: #1a1f2e; border-radius: 8px; padding: 16px 20px; flex: 1; }
.stat-card .label { font-size: 11px; color: #4a5568; letter-spacing: .06em; margin-bottom: 6px; }
.stat-card .value { font-size: 28px; font-weight: 700; }

.btn { padding: 8px 18px; border: none; border-radius: 6px; font-size: 14px; cursor: pointer; font-weight: 500; }
.btn-primary { background: #3b82f6; color: #fff; }
.btn-primary:hover { background: #2563eb; }
.btn-success { background: #10b981; color: #fff; }
.btn-ghost { background: rgba(255,255,255,.08); color: #a0aec0; }
.btn-ghost:hover { background: rgba(255,255,255,.14); }
.btn-danger { background: rgba(239,68,68,.15); color: #f87171; }
.btn:disabled { opacity: .5; cursor: default; }

.progress-wrap { background: #2d3748; border-radius: 4px; height: 6px; margin: 10px 0; overflow: hidden; }
.progress-bar { background: #3b82f6; height: 100%; border-radius: 4px; transition: width .4s ease; }

.pills { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.pill { padding: 5px 14px; border-radius: 20px; font-size: 13px; cursor: pointer;
        background: rgba(255,255,255,.08); color: #a0aec0; border: 1px solid transparent; }
.pill.selected { background: rgba(59,130,246,.2); color: #60a5fa; border-color: rgba(59,130,246,.4); }

.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; padding: 10px 14px; font-size: 11px; color: #4a5568; font-weight: 500;
     letter-spacing: .04em; border-bottom: 1px solid #2d3748; }
td { padding: 9px 14px; border-top: 1px solid rgba(255,255,255,.04); }
tr:hover td { background: rgba(255,255,255,.02); }
.bill-num { font-family: monospace; color: #60a5fa; white-space: nowrap; }

.category-layout { display: flex; gap: 20px; align-items: flex-start; }
.category-list { width: 220px; min-width: 220px; }
.category-item { padding: 10px 14px; border-radius: 6px; cursor: pointer;
                  margin-bottom: 6px; background: rgba(255,255,255,.04); }
.category-item.selected { background: rgba(59,130,246,.15); border: 1px solid rgba(59,130,246,.35); }
.category-item .cat-name { font-size: 14px; }
.category-item .cat-count { font-size: 11px; color: #4a5568; margin-top: 2px; }
.keyword-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.chip { display: flex; align-items: center; gap: 6px; background: rgba(255,255,255,.1);
        border-radius: 20px; padding: 4px 10px; font-size: 12px; }
.chip-remove { opacity: .4; cursor: pointer; font-size: 14px; }
.chip-remove:hover { opacity: 1; }

.form-group { margin-bottom: 18px; }
.form-group label { display: block; font-size: 12px; color: #4a5568; margin-bottom: 6px; }
input[type="text"], input[type="email"], input[type="password"] {
  width: 100%; padding: 9px 12px; background: #1a1f2e;
  border: 1px solid #2d3748; border-radius: 6px; color: #e2e8f0; font-size: 14px;
}
input:focus { outline: none; border-color: #3b82f6; }
.form-card { max-width: 400px; margin: 80px auto; background: #1a1f2e; padding: 32px; border-radius: 10px; }
.form-card h2 { margin-bottom: 24px; }
.form-footer { margin-top: 14px; font-size: 13px; color: #4a5568; }
.form-footer a { color: #3b82f6; text-decoration: none; }
.error-msg { color: #f87171; font-size: 13px; margin-top: 8px; }
.section-title { font-size: 18px; font-weight: 600; margin-bottom: 20px; }
.toolbar { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
.bill-count { font-size: 13px; color: #4a5568; }
```

- [ ] **Step 2: Write `static/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bill Tracker</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <nav id="nav"></nav>
  <main id="app"></main>
  <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Write `static/app.js` — routing skeleton**

```javascript
// ── Escape helper: sanitize API/user data before inserting into innerHTML ──
function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}

// ── State ──────────────────────────────────────────────────────────────────
let currentUser = null;

// ── API helpers ────────────────────────────────────────────────────────────
async function api(method, path, body) {
  const opts = { method, headers: {} };
  if (body) {
    opts.body = JSON.stringify(body);
    opts.headers['Content-Type'] = 'application/json';
  }
  const r = await fetch('/api' + path, opts);
  if (r.status === 401 && path !== '/auth/me') { navigate('/login'); return null; }
  return r;
}

// ── Navigation ─────────────────────────────────────────────────────────────
function navigate(path) {
  history.pushState({}, '', path);
  render();
}

window.addEventListener('popstate', render);

function render() {
  const path = window.location.pathname;
  const publicPaths = ['/login', '/signup'];
  if (!currentUser && !publicPaths.includes(path)) { renderLogin(); return; }
  if (currentUser) updateNav(path);
  if (path === '/' || path === '') renderDashboard();
  else if (path === '/bills') renderBills();
  else if (path === '/categories') renderCategories();
  else if (path === '/login') renderLogin();
  else if (path === '/signup') renderSignup();
  else document.getElementById('app').textContent = 'Page not found.';
}

function updateNav(activePath) {
  const nav = document.getElementById('nav');
  nav.innerHTML = '';

  const links = [
    ['/', 'Dashboard'],
    ['/bills', 'Browse Bills'],
    ['/categories', 'My Categories'],
  ];
  links.forEach(([href, label]) => {
    const a = document.createElement('a');
    a.href = href;
    a.textContent = label;
    if (activePath === href) a.classList.add('active');
    a.addEventListener('click', (e) => { e.preventDefault(); navigate(href); });
    nav.appendChild(a);
  });

  const spacer = document.createElement('div');
  spacer.className = 'spacer';
  nav.appendChild(spacer);

  const info = document.createElement('span');
  info.className = 'user-info';
  info.textContent = currentUser.email;
  nav.appendChild(info);

  const logoutBtn = document.createElement('button');
  logoutBtn.className = 'logout-btn';
  logoutBtn.textContent = 'Logout';
  logoutBtn.addEventListener('click', logout);
  nav.appendChild(logoutBtn);
}

async function logout() {
  await api('POST', '/auth/logout');
  currentUser = null;
  document.getElementById('nav').innerHTML = '';
  navigate('/login');
}

// ── Bootstrap ──────────────────────────────────────────────────────────────
async function init() {
  const r = await fetch('/api/auth/me');
  if (r.ok) currentUser = await r.json();
  render();
}

init();
```

- [ ] **Step 4: Verify shell loads without JS errors**

```bash
uvicorn main:app --reload
```

Open http://localhost:8000 — should see an empty page (no nav yet since not logged in). Open browser DevTools console — no errors. Navigating to `/login` should not crash.

- [ ] **Step 5: Commit**

```bash
git add static/
git commit -m "feat: frontend shell — routing, nav, CSS, XSS-safe esc() helper"
```

---

## Task 11: Auth Pages

**Files:**
- Modify: `static/app.js` (append login and signup page functions)

- [ ] **Step 1: Append to `static/app.js`**

```javascript
// ── Login Page ─────────────────────────────────────────────────────────────
function renderLogin() {
  document.getElementById('nav').innerHTML = '';
  const app = document.getElementById('app');
  app.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'form-card';
  card.innerHTML = '<h2>Sign in</h2>';

  card.appendChild(makeInput('login-email', 'Email', 'email'));
  card.appendChild(makeInput('login-password', 'Password', 'password'));

  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.style.width = '100%';
  btn.textContent = 'Sign in';
  btn.addEventListener('click', doLogin);
  card.appendChild(btn);

  const err = document.createElement('div');
  err.id = 'login-error';
  err.className = 'error-msg';
  card.appendChild(err);

  const footer = document.createElement('div');
  footer.className = 'form-footer';
  footer.innerHTML = "No account? ";
  const link = document.createElement('a');
  link.href = '/signup';
  link.textContent = 'Sign up';
  link.addEventListener('click', (e) => { e.preventDefault(); navigate('/signup'); });
  footer.appendChild(link);
  card.appendChild(footer);

  app.appendChild(card);
}

async function doLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const r = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (r.ok) {
    currentUser = await r.json();
    navigate('/');
  } else {
    const data = await r.json();
    document.getElementById('login-error').textContent = data.detail || 'Login failed';
  }
}

// ── Signup Page ────────────────────────────────────────────────────────────
function renderSignup() {
  document.getElementById('nav').innerHTML = '';
  const app = document.getElementById('app');
  app.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'form-card';
  card.innerHTML = '<h2>Create account</h2>';

  card.appendChild(makeInput('signup-email', 'Email', 'email'));
  card.appendChild(makeInput('signup-password', 'Password', 'password'));

  const btn = document.createElement('button');
  btn.className = 'btn btn-primary';
  btn.style.width = '100%';
  btn.textContent = 'Create account';
  btn.addEventListener('click', doSignup);
  card.appendChild(btn);

  const err = document.createElement('div');
  err.id = 'signup-error';
  err.className = 'error-msg';
  card.appendChild(err);

  const footer = document.createElement('div');
  footer.className = 'form-footer';
  footer.innerHTML = 'Already have an account? ';
  const link = document.createElement('a');
  link.href = '/login';
  link.textContent = 'Sign in';
  link.addEventListener('click', (e) => { e.preventDefault(); navigate('/login'); });
  footer.appendChild(link);
  card.appendChild(footer);

  app.appendChild(card);
}

async function doSignup() {
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const r = await fetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (r.ok) {
    currentUser = await r.json();
    navigate('/');
  } else {
    const data = await r.json();
    document.getElementById('signup-error').textContent = data.detail || 'Signup failed';
  }
}

// ── Shared form helpers ────────────────────────────────────────────────────
function makeInput(id, labelText, type) {
  const group = document.createElement('div');
  group.className = 'form-group';
  const label = document.createElement('label');
  label.textContent = labelText;
  const input = document.createElement('input');
  input.type = type;
  input.id = id;
  group.appendChild(label);
  group.appendChild(input);
  return group;
}
```

- [ ] **Step 2: Manually verify**

1. Go to http://localhost:8000 → redirects to login form
2. Click Sign up → signup form
3. Create account → lands on blank Dashboard
4. Logout → login form
5. Sign back in → Dashboard

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: login and signup pages"
```

---

## Task 12: Dashboard Page

**Files:**
- Modify: `static/app.js` (append dashboard functions)

- [ ] **Step 1: Append to `static/app.js`**

```javascript
// ── Dashboard Page ─────────────────────────────────────────────────────────
let _pollInterval = null;

async function renderDashboard() {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'section-title';
  title.textContent = 'Dashboard';
  app.appendChild(title);

  const cards = document.createElement('div');
  cards.className = 'stat-cards';
  cards.innerHTML = `
    <div class="stat-card"><div class="label">TOTAL BILLS</div><div class="value" id="stat-bills">—</div></div>
    <div class="stat-card"><div class="label">LAST SYNCED</div><div class="value" id="stat-synced" style="font-size:18px">—</div></div>
    <div class="stat-card"><div class="label">MY CATEGORIES</div><div class="value" id="stat-cats">—</div></div>
  `;
  app.appendChild(cards);

  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  toolbar.innerHTML = `
    <button class="btn btn-primary" id="fetch-btn">&#x21BB; Fetch Bills</button>
    <span id="fetch-status-text" style="font-size:13px;color:#4a5568"></span>
  `;
  app.appendChild(toolbar);
  document.getElementById('fetch-btn').addEventListener('click', startFetch);

  const progressWrap = document.createElement('div');
  progressWrap.className = 'progress-wrap';
  progressWrap.id = 'progress-wrap';
  progressWrap.style.display = 'none';
  progressWrap.innerHTML = '<div class="progress-bar" id="progress-bar" style="width:0%"></div>';
  app.appendChild(progressWrap);

  loadDashboardStats();
  checkActiveFetch();
}

async function loadDashboardStats() {
  const [billsR, catsR, latestR] = await Promise.all([
    api('GET', '/bills?limit=1'),
    api('GET', '/categories'),
    api('GET', '/fetch/latest'),
  ]);
  if (!billsR) return;
  const [bills, cats, latest] = await Promise.all([billsR.json(), catsR.json(), latestR.json()]);

  const statBills = document.getElementById('stat-bills');
  if (statBills) statBills.textContent = bills.total.toLocaleString();
  const statCats = document.getElementById('stat-cats');
  if (statCats) statCats.textContent = cats.length;
  const statSynced = document.getElementById('stat-synced');
  if (statSynced && latest && latest.finished_at) {
    statSynced.textContent = new Date(latest.finished_at).toLocaleString();
  }
}

async function checkActiveFetch() {
  const r = await api('GET', '/fetch/latest');
  if (!r) return;
  const job = await r.json();
  if (job && (job.status === 'queued' || job.status === 'running')) {
    startPolling(job.id);
  }
}

async function startFetch() {
  const btn = document.getElementById('fetch-btn');
  if (btn) btn.disabled = true;
  const r = await api('POST', '/fetch');
  if (!r) return;
  const data = await r.json();
  startPolling(data.job_id);
}

function startPolling(jobId) {
  clearInterval(_pollInterval);
  const wrap = document.getElementById('progress-wrap');
  if (wrap) wrap.style.display = 'block';

  _pollInterval = setInterval(async () => {
    const r = await api('GET', `/fetch/status/${jobId}`);
    if (!r) return;
    const job = await r.json();
    const pct = job.total_bills ? Math.round((job.bills_fetched / job.total_bills) * 100) : 0;
    const bar = document.getElementById('progress-bar');
    if (bar) bar.style.width = pct + '%';
    const statusText = document.getElementById('fetch-status-text');
    if (statusText) {
      statusText.textContent = job.total_bills
        ? 'Syncing… ' + job.bills_fetched.toLocaleString() + ' / ' + job.total_bills.toLocaleString()
        : 'Starting…';
    }
    if (job.status === 'done' || job.status === 'failed') {
      clearInterval(_pollInterval);
      const btn = document.getElementById('fetch-btn');
      if (btn) btn.disabled = false;
      if (bar) bar.style.width = job.status === 'done' ? '100%' : bar.style.width;
      if (statusText) {
        statusText.textContent = job.status === 'done'
          ? 'Done — ' + job.bills_updated + ' bills updated'
          : 'Error: ' + (job.error_msg || 'unknown');
      }
      if (job.status === 'done') loadDashboardStats();
    }
  }, 3000);
}
```

- [ ] **Step 2: Manually verify**

1. Sign in → Dashboard shows stat cards loading
2. Click **Fetch Bills** → progress bar appears, status text updates every 3s
3. (Kill after a few seconds if you don't want a full sync)

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: dashboard — stats, fetch button, progress polling"
```

---

## Task 13: Browse Bills Page

**Files:**
- Modify: `static/app.js` (append bills page functions)

- [ ] **Step 1: Append to `static/app.js`**

```javascript
// ── Browse Bills Page ──────────────────────────────────────────────────────
let _billsState = { categories: [], selectedIds: [], page: 1, total: 0 };

async function renderBills() {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'section-title';
  title.textContent = 'Browse Bills';
  app.appendChild(title);

  const filterLabel = document.createElement('div');
  filterLabel.style = 'font-size:12px;color:#4a5568;margin-bottom:8px';
  filterLabel.textContent = 'Filter by category:';
  app.appendChild(filterLabel);

  const pills = document.createElement('div');
  pills.className = 'pills';
  pills.id = 'category-pills';
  app.appendChild(pills);

  const toolbar = document.createElement('div');
  toolbar.className = 'toolbar';
  toolbar.innerHTML = `
    <button class="btn btn-primary" id="filter-btn">Filter Bills</button>
    <button class="btn btn-ghost" id="clear-btn">Clear</button>
    <span class="bill-count" id="bill-count"></span>
    <div style="flex:1"></div>
    <button class="btn btn-success" id="export-btn">&#x2B07; Export CSV</button>
  `;
  app.appendChild(toolbar);
  document.getElementById('filter-btn').addEventListener('click', () => loadBillsPage(1));
  document.getElementById('clear-btn').addEventListener('click', clearBillsFilter);
  document.getElementById('export-btn').addEventListener('click', exportCSV);

  const tableWrap = document.createElement('div');
  tableWrap.className = 'table-wrap';
  tableWrap.innerHTML = `
    <table>
      <thead><tr>
        <th>Bill #</th><th>Title</th><th>Chamber</th>
        <th>Committee</th><th>Last Action</th><th>Status</th>
      </tr></thead>
      <tbody id="bills-tbody"></tbody>
    </table>
  `;
  app.appendChild(tableWrap);

  const pagination = document.createElement('div');
  pagination.id = 'bills-pagination';
  pagination.style = 'margin-top:14px;display:flex;gap:8px;align-items:center';
  app.appendChild(pagination);

  const r = await api('GET', '/categories');
  if (!r) return;
  _billsState.categories = await r.json();
  _billsState.selectedIds = [];
  _billsState.page = 1;
  renderBillsPills();
  loadBillsPage(1);
}

function renderBillsPills() {
  const pills = document.getElementById('category-pills');
  if (!pills) return;
  pills.innerHTML = '';
  _billsState.categories.forEach(c => {
    const pill = document.createElement('div');
    pill.className = 'pill' + (_billsState.selectedIds.includes(c.id) ? ' selected' : '');
    pill.textContent = c.name;
    pill.addEventListener('click', () => toggleBillsPill(c.id));
    pills.appendChild(pill);
  });
}

function toggleBillsPill(id) {
  if (_billsState.selectedIds.includes(id)) {
    _billsState.selectedIds = _billsState.selectedIds.filter(x => x !== id);
  } else {
    _billsState.selectedIds.push(id);
  }
  renderBillsPills();
}

async function loadBillsPage(page) {
  _billsState.page = page;
  let r;
  if (_billsState.selectedIds.length) {
    r = await api('POST', '/bills/filter?page=' + page, { category_ids: _billsState.selectedIds });
  } else {
    r = await api('GET', '/bills?page=' + page);
  }
  if (!r) return;
  const data = await r.json();
  _billsState.total = data.total;
  renderBillsTable(data.bills);
  renderBillsPagination(data.total, page);
  const count = document.getElementById('bill-count');
  if (count) count.textContent = 'Showing ' + data.bills.length + ' of ' + data.total.toLocaleString() + ' bills';
}

function renderBillsTable(bills) {
  const tbody = document.getElementById('bills-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  bills.forEach(b => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="bill-num">${esc(b.number)}</td>
      <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="${esc(b.title)}">${esc(b.title)}</td>
      <td>${esc(b.chamber)}</td>
      <td style="color:#718096">${esc(b.committee || '—')}</td>
      <td style="color:#718096;white-space:nowrap">${esc(b.last_action_date)}</td>
      <td><span style="background:rgba(59,130,246,.12);color:#60a5fa;border-radius:4px;padding:2px 8px;font-size:11px">${esc(b.status)}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderBillsPagination(total, page) {
  const el = document.getElementById('bills-pagination');
  if (!el) return;
  el.innerHTML = '';
  const totalPages = Math.ceil(total / 50);
  if (page > 1) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost';
    btn.textContent = '← Prev';
    btn.addEventListener('click', () => loadBillsPage(page - 1));
    el.appendChild(btn);
  }
  const info = document.createElement('span');
  info.style = 'font-size:13px;color:#4a5568';
  info.textContent = 'Page ' + page + ' of ' + totalPages;
  el.appendChild(info);
  if (page < totalPages) {
    const btn = document.createElement('button');
    btn.className = 'btn btn-ghost';
    btn.textContent = 'Next →';
    btn.addEventListener('click', () => loadBillsPage(page + 1));
    el.appendChild(btn);
  }
}

function clearBillsFilter() {
  _billsState.selectedIds = [];
  renderBillsPills();
  loadBillsPage(1);
}

function exportCSV() {
  const ids = _billsState.selectedIds.join(',');
  window.location.href = '/api/bills/export?category_ids=' + ids;
}
```

- [ ] **Step 2: Manually verify**

1. Go to Browse Bills — table loads with all bills
2. Click a category pill → Filter Bills → table narrows
3. Click Export CSV → file downloads

- [ ] **Step 3: Commit**

```bash
git add static/app.js
git commit -m "feat: browse bills — filter, table, pagination, export"
```

---

## Task 14: My Categories Page

**Files:**
- Modify: `static/app.js` (append categories page functions)

- [ ] **Step 1: Append to `static/app.js`**

```javascript
// ── My Categories Page ─────────────────────────────────────────────────────
let _catsState = { categories: [], selectedId: null };

async function renderCategories() {
  const app = document.getElementById('app');
  app.innerHTML = '';

  const title = document.createElement('div');
  title.className = 'section-title';
  title.textContent = 'My Categories';
  app.appendChild(title);

  const layout = document.createElement('div');
  layout.className = 'category-layout';
  layout.innerHTML = `
    <div class="category-list" id="cat-list"></div>
    <div style="flex:1" id="cat-editor">
      <p style="color:#4a5568">Select a category or create one.</p>
    </div>
  `;
  app.appendChild(layout);

  const r = await api('GET', '/categories');
  if (!r) return;
  _catsState.categories = await r.json();
  _catsState.selectedId = null;
  renderCatList();
}

function renderCatList() {
  const list = document.getElementById('cat-list');
  if (!list) return;
  list.innerHTML = '';

  _catsState.categories.forEach(c => {
    const item = document.createElement('div');
    item.className = 'category-item' + (c.id === _catsState.selectedId ? ' selected' : '');
    item.innerHTML = `
      <div class="cat-name">${esc(c.name)}</div>
      <div class="cat-count">${c.keywords.length} keyword${c.keywords.length !== 1 ? 's' : ''}</div>
    `;
    item.addEventListener('click', () => selectCat(c.id));
    list.appendChild(item);
  });

  const newBtn = document.createElement('button');
  newBtn.className = 'btn btn-ghost';
  newBtn.style = 'width:100%;margin-top:8px;font-size:13px';
  newBtn.textContent = '+ New Category';
  newBtn.addEventListener('click', createCat);
  list.appendChild(newBtn);
}

function selectCat(id) {
  _catsState.selectedId = id;
  renderCatList();
  const cat = _catsState.categories.find(c => c.id === id);
  if (cat) renderCatEditor(cat);
}

function renderCatEditor(cat) {
  const editor = document.getElementById('cat-editor');
  if (!editor) return;
  editor.innerHTML = '';

  const header = document.createElement('div');
  header.style = 'display:flex;align-items:center;gap:10px;margin-bottom:16px';
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.id = 'cat-name-input';
  nameInput.value = cat.name;
  nameInput.style = 'font-size:16px;font-weight:600;flex:1';
  const deleteBtn = document.createElement('button');
  deleteBtn.className = 'btn btn-danger';
  deleteBtn.textContent = 'Delete';
  deleteBtn.addEventListener('click', () => deleteCat(cat.id));
  header.appendChild(nameInput);
  header.appendChild(deleteBtn);
  editor.appendChild(header);

  const kwLabel = document.createElement('div');
  kwLabel.style = 'font-size:11px;color:#4a5568;letter-spacing:.05em;margin-bottom:8px';
  kwLabel.textContent = 'KEYWORDS — bills containing any of these are included';
  editor.appendChild(kwLabel);

  const chips = document.createElement('div');
  chips.className = 'keyword-chips';
  chips.id = 'chip-list';
  cat.keywords.forEach(kw => {
    const chip = document.createElement('div');
    chip.className = 'chip';
    const kwText = document.createElement('span');
    kwText.textContent = kw;
    const removeBtn = document.createElement('span');
    removeBtn.className = 'chip-remove';
    removeBtn.textContent = '\xD7';
    removeBtn.addEventListener('click', () => removeKeyword(cat, kw));
    chip.appendChild(kwText);
    chip.appendChild(removeBtn);
    chips.appendChild(chip);
  });
  editor.appendChild(chips);

  const addRow = document.createElement('div');
  addRow.style = 'display:flex;gap:8px;margin-bottom:16px';
  const kwInput = document.createElement('input');
  kwInput.type = 'text';
  kwInput.id = 'kw-input';
  kwInput.placeholder = 'Add keyword, press Enter…';
  kwInput.style = 'flex:1';
  kwInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addKeyword(cat); });
  const addBtn = document.createElement('button');
  addBtn.className = 'btn btn-ghost';
  addBtn.textContent = 'Add';
  addBtn.addEventListener('click', () => addKeyword(cat));
  addRow.appendChild(kwInput);
  addRow.appendChild(addBtn);
  editor.appendChild(addRow);

  const saveRow = document.createElement('div');
  const saveBtn = document.createElement('button');
  saveBtn.className = 'btn btn-primary';
  saveBtn.textContent = 'Save Category';
  saveBtn.addEventListener('click', () => saveCat(cat));
  const saveMsg = document.createElement('span');
  saveMsg.id = 'save-msg';
  saveMsg.style = 'font-size:13px;color:#10b981;margin-left:12px';
  saveRow.appendChild(saveBtn);
  saveRow.appendChild(saveMsg);
  editor.appendChild(saveRow);
}

function addKeyword(cat) {
  const input = document.getElementById('kw-input');
  if (!input) return;
  const kw = input.value.trim().toLowerCase();
  if (!kw || cat.keywords.includes(kw)) { input.value = ''; return; }
  cat.keywords.push(kw);
  renderCatEditor(cat);
}

function removeKeyword(cat, kw) {
  cat.keywords = cat.keywords.filter(k => k !== kw);
  renderCatEditor(cat);
}

async function saveCat(cat) {
  const nameInput = document.getElementById('cat-name-input');
  const name = nameInput ? nameInput.value.trim() : cat.name;
  const r = await api('PUT', '/categories/' + cat.id, { name, keywords: cat.keywords });
  if (!r || !r.ok) return;
  const updated = await r.json();
  Object.assign(cat, updated);
  renderCatList();
  const msg = document.getElementById('save-msg');
  if (msg) {
    msg.textContent = 'Saved!';
    setTimeout(() => { if (msg) msg.textContent = ''; }, 2000);
  }
}

async function deleteCat(id) {
  if (!confirm('Delete this category?')) return;
  const r = await api('DELETE', '/categories/' + id);
  if (!r || !r.ok) return;
  _catsState.categories = _catsState.categories.filter(c => c.id !== id);
  _catsState.selectedId = null;
  renderCatList();
  const editor = document.getElementById('cat-editor');
  if (editor) editor.innerHTML = '<p style="color:#4a5568">Select a category or create one.</p>';
}

async function createCat() {
  const r = await api('POST', '/categories', { name: 'New Category', keywords: [] });
  if (!r || !r.ok) return;
  const cat = await r.json();
  _catsState.categories.push(cat);
  _catsState.selectedId = cat.id;
  renderCatList();
  renderCatEditor(cat);
}
```

- [ ] **Step 2: Manually verify**

1. Go to My Categories
2. Click **+ New Category** → editor opens
3. Rename, add keywords, click Save → persists on page refresh
4. Delete a category → removed from list

- [ ] **Step 3: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat: my categories page — keyword editor"
```

---

## Task 15: Deployment Config

**Files:**
- Create: `Procfile`
- Create: `render.yaml`
- Update: `CLAUDE.md`

- [ ] **Step 1: Write `Procfile`**

```
web: uvicorn main:app --host 0.0.0.0 --port $PORT
```

- [ ] **Step 2: Write `render.yaml`**

```yaml
services:
  - type: web
    name: bill-tracker
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: bill-tracker-db
          property: connectionString
      - key: LEGISCAN_API_KEY
        sync: false   # set manually in Render dashboard

databases:
  - name: bill-tracker-db
    databaseName: bill_tracker
    plan: free
```

- [ ] **Step 3: Update `CLAUDE.md`**

Replace the existing `CLAUDE.md` at `/Users/raphaelchen/Desktop/bill_tracker/CLAUDE.md` with:

```markdown
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running Locally

```bash
source venv/bin/activate
pip install -r requirements.txt
createdb bill_tracker          # one-time
psql bill_tracker < migrations/001_initial.sql  # one-time
cp .env.example .env           # fill in DATABASE_URL and LEGISCAN_API_KEY
uvicorn main:app --reload
```

Open http://localhost:8000.

## Running Tests

```bash
createdb bill_tracker_test     # one-time
DATABASE_URL=postgresql://localhost/bill_tracker_test pytest -v
```

## Architecture

FastAPI backend + plain HTML/JS frontend. All routes under `/api/*` are JSON endpoints; everything else returns `static/index.html` (client-side routing via `history.pushState`). `main.py` wires the four routers and static file mount together.

**Backend layers:**
- `database.py` — psycopg2 `ThreadedConnectionPool`; use `get_conn()` context manager for all DB access
- `auth.py` — bcrypt password hashing, 32-byte hex session tokens in `sessions` table, `get_current_user()` FastAPI dependency
- `routers/` — one file per endpoint group
- `services/legiscan.py` — `fetch_master_list()` + `sync_bills()`, ported from original script; runs as a `BackgroundTask` from `routers/fetch.py`
- `services/filter.py` — `filter_bills()` uses `ILIKE ANY(ARRAY[...])` for case-insensitive keyword matching

**Frontend:** `static/app.js` is a single file with all page render functions. Use the `esc()` helper when interpolating API data into innerHTML to prevent XSS. No build step.

## Key Behaviors

- **Cache logic:** bills re-fetch from LegiScan only when `last_action_date` changes; the `bills` table is the shared cache
- **Fetch deduplication:** `POST /api/fetch` returns the existing job if one is `queued` or `running`
- **Filter isolation:** `filter_bills()` joins `categories WHERE user_id = %s` — users cannot use each other's keyword sets
- **Session expiry:** 30 days; expired sessions require re-login

## Deployment (Render)

1. Push to GitHub
2. New Web Service → connect repo → Render uses `render.yaml` automatically
3. Set `LEGISCAN_API_KEY` in Render environment dashboard
4. After first deploy, run migration once via Render shell: `psql $DATABASE_URL < migrations/001_initial.sql`
```

- [ ] **Step 4: Final test run**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add Procfile render.yaml CLAUDE.md
git commit -m "chore: deployment config, updated CLAUDE.md"
```
