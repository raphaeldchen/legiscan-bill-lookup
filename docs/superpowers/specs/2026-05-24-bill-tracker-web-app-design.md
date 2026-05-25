# Bill Tracker Web App — Design Spec

**Date:** 2026-05-24
**Status:** Approved

## Overview

Convert the single-script `criminaljustice.py` LegiScan pipeline into a multi-user web application for a team of interns. Each intern has their own account and maintains their own named keyword categories. A shared bill cache (PostgreSQL) is fetched from the LegiScan API on demand. Interns filter the shared bill pool by their own categories and export results as CSV.

**Scope constraints (v1):**
- Illinois only (no state selection)
- Keyword-only filtering (no LLM evaluation)
- No email verification, no password reset, no OAuth

---

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI (Python) |
| Frontend | Plain HTML + vanilla JavaScript, served by FastAPI |
| Database | PostgreSQL |
| Auth | bcrypt passwords + httponly session cookie |
| Deployment | PaaS (Railway or Render) |
| LegiScan API key | Environment variable `LEGISCAN_API_KEY` |

---

## Data Model

### `users`
```
id            SERIAL PRIMARY KEY
email         TEXT UNIQUE NOT NULL
password_hash TEXT NOT NULL
created_at    TIMESTAMPTZ DEFAULT now()
```

### `sessions`
```
id          SERIAL PRIMARY KEY
user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE
token       TEXT UNIQUE NOT NULL          -- random 32-byte hex
created_at  TIMESTAMPTZ DEFAULT now()
expires_at  TIMESTAMPTZ NOT NULL          -- created_at + 30 days
```

### `bills`
Shared across all users — the persistent cache replacing `bill_cache.json`.
```
bill_id          TEXT PRIMARY KEY          -- LegiScan bill_id (string key)
number           TEXT
title            TEXT
description      TEXT
status           TEXT
chamber          TEXT                      -- 'House' | 'Senate' | 'Unknown'
committee        TEXT
sponsors         TEXT                      -- semicolon-separated names
last_action      TEXT
last_action_date TEXT                      -- cache invalidation key
raw_json         JSONB                     -- full LegiScan getBill response
fetched_at       TIMESTAMPTZ DEFAULT now()
```
A bill is re-fetched from LegiScan only when its `last_action_date` changes, matching the original script's cache logic.

### `categories`
Per-user named keyword sets.
```
id         SERIAL PRIMARY KEY
user_id    INTEGER REFERENCES users(id) ON DELETE CASCADE
name       TEXT NOT NULL
keywords   TEXT[]                          -- e.g. ['felony', 'police', 'incarcerated']
created_at TIMESTAMPTZ DEFAULT now()
updated_at TIMESTAMPTZ DEFAULT now()
```

### `fetch_jobs`
Tracks background fetch runs.
```
id            SERIAL PRIMARY KEY
status        TEXT DEFAULT 'queued'        -- queued | running | done | failed
started_at    TIMESTAMPTZ
finished_at   TIMESTAMPTZ
total_bills   INTEGER
bills_fetched INTEGER DEFAULT 0            -- progress counter
bills_updated INTEGER DEFAULT 0           -- how many were stale and re-fetched
error_msg     TEXT
```

---

## Project Structure

```
bill_tracker/
├── main.py                  # FastAPI app, mounts routers and static files
├── database.py              # asyncpg connection pool setup
├── models.py                # Pydantic request/response schemas
├── auth.py                  # session middleware, password hashing
├── routers/
│   ├── auth.py              # /api/auth/*
│   ├── bills.py             # /api/bills/*
│   ├── fetch.py             # /api/fetch/*
│   └── categories.py        # /api/categories/*
├── services/
│   ├── legiscan.py          # fetch_master_list(), sync_bills() — ported from criminaljustice.py
│   └── filter.py            # keyword filtering SQL logic
├── static/
│   ├── index.html           # single HTML shell, JS handles routing
│   ├── app.js               # page routing + API calls
│   └── style.css
└── criminaljustice.py       # original script (kept for reference)
```

---

## API Endpoints

All endpoints under `/api`. All except `/api/auth/login` and `/api/auth/signup` require a valid session cookie.

### Auth
```
POST /api/auth/signup        body: {email, password} → sets cookie, returns {user}
POST /api/auth/login         body: {email, password} → sets cookie, returns {user}
POST /api/auth/logout        clears cookie, deletes session row
GET  /api/auth/me            returns {id, email} or 401
```

### Bills
```
GET  /api/bills              ?page=1&limit=50 → paginated bill list
POST /api/bills/filter       body: {category_ids: [1,2]} → paginated filtered bills
GET  /api/bills/export       ?category_ids=1,2 → streams CSV download
```

### Fetch
```
POST /api/fetch              starts background sync; if one is already running,
                             returns the existing job_id instead of starting a new one
GET  /api/fetch/status/{id} returns {status, total_bills, bills_fetched,
                             bills_updated, error_msg}
GET  /api/fetch/latest       returns the most recent fetch_job row
                             (used by Dashboard to show "Last synced" on load)
```

### Categories
```
GET    /api/categories        returns this user's categories
POST   /api/categories        body: {name, keywords: []} → creates category
PUT    /api/categories/{id}   body: {name?, keywords?} → updates
DELETE /api/categories/{id}   deletes
```

---

## Pages & Routing

Single `index.html` shell; vanilla JS swaps page content based on `window.location.hash` or path. The FastAPI catch-all route returns `index.html` for any non-`/api` path.

**Unauthenticated routes:** `/login`, `/signup`
**Authenticated routes:** `/` (Dashboard), `/bills`, `/categories`

On every page load, JS calls `GET /api/auth/me`; a 401 response redirects to `/login`.

### Navigation
Top tab bar: **Dashboard · Browse Bills · My Categories** + email + Logout link.

### Dashboard (`/`)
- Stat cards: Total Bills, Last Synced, My Categories count
- **Fetch Bills** button → `POST /api/fetch` → polls `/api/fetch/status/{id}` every 3s → progress bar `"Syncing… 1,247 / 5,832"`
- On completion, stat cards refresh

### Browse Bills (`/bills`)
- Category pills (the user's categories) — clickable to select/deselect, multi-select
- **Filter Bills** button → `POST /api/bills/filter` → table updates in place
- **Clear** button resets to unfiltered view
- Bill count shown (`"Showing 312 of 5,832"`)
- **Export CSV** button → `GET /api/bills/export?category_ids=...` → file download
- Paginated table: Bill #, Title, Chamber, Committee, Last Action, Status

### My Categories (`/categories`)
- Left panel: list of this user's categories (click to select)
- Right panel: editable category name + keyword tag editor (add/remove chips)
- **Save Category** button → `PUT /api/categories/{id}`
- **Delete** button with confirmation
- **+ New Category** button

---

## Auth Flow

1. **Signup/Login:** email + password → bcrypt verify → create/lookup session row → set `HttpOnly; SameSite=Lax` cookie with 30-day expiry → redirect to Dashboard
2. **Request auth:** FastAPI middleware reads cookie → looks up session in DB → checks `expires_at` → attaches user to `request.state.user`, or returns 401
3. **Logout:** DELETE session row, clear cookie

No email verification, no password reset in v1.

---

## Fetch & Filter Flow

### Fetch Bills (background task)
1. `POST /api/fetch` — creates a `fetch_jobs` row (`status: queued`), returns `{job_id}`
2. If a `queued` or `running` job already exists, returns that job's ID (no duplicate runs)
3. FastAPI `BackgroundTasks` runs `services/legiscan.py`:
   - `fetch_master_list()` — calls LegiScan `getMasterList` for IL, returns bill stubs
   - `sync_bills(stubs, job_id)` — for each stub, checks DB for matching `bill_id` + `last_action_date`; if stale or missing, calls `getBill` and upserts; updates `bills_fetched` counter on the job row after each bill
4. Frontend polls `GET /api/fetch/status/{job_id}` every 3 seconds; renders progress bar
5. On `status: done`, Dashboard stats refresh

Retry logic from original script preserved: 3 attempts with 3-second delay on API failure.

### Filter Bills (fast, synchronous)
1. `POST /api/bills/filter` with `{category_ids: [1, 3]}`
2. Backend collects all `keywords` arrays from those categories (for this user only)
3. Single SQL query:
   ```sql
   SELECT * FROM bills
   WHERE description ILIKE ANY(ARRAY['%felony%', '%police%', ...])
   ORDER BY last_action_date DESC
   LIMIT 50 OFFSET 0
   ```
4. Returns paginated `{bills, total, page}` — table updates in place
5. Export: same query, streamed as CSV via `StreamingResponse`

---

## Deployment

- **Environment variables:** `LEGISCAN_API_KEY`, `DATABASE_URL`
- **Database migrations:** plain SQL files in `migrations/` run once on deploy (no ORM migration tool in v1)
- **Static files:** FastAPI `StaticFiles` mount serves `static/` at `/`
- **PaaS config:** single `Procfile` or `railway.toml` / `render.yaml` with `uvicorn main:app --host 0.0.0.0 --port $PORT`

---

## Out of Scope (v1)

- LLM-based guideline filtering
- Multi-state support
- Password reset / email verification
- Admin panel
- Scheduled automatic fetches (APScheduler — easy to add in v2)
- Real-time WebSocket progress (polling is sufficient)
