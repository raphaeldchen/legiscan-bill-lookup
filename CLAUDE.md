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
- `routers/` — one file per endpoint group (auth, categories, fetch, bills)
- `services/legiscan.py` — `fetch_master_list()` + `sync_bills()`, ported from original script; runs as a `BackgroundTask` from `routers/fetch.py`
- `services/filter.py` — `filter_bills()` uses per-condition `ILIKE %s ESCAPE '!'` for case-insensitive, literal keyword matching

**Frontend:** `static/app.js` is a single file with all page render functions. Use the `esc()` helper when interpolating API data into innerHTML to prevent XSS. No build step.

## Key Behaviors

- **Cache logic:** bills re-fetch from LegiScan only when `last_action_date` changes; the `bills` table is the shared cache
- **Fetch deduplication:** `POST /api/fetch` returns the existing job if one is `queued` or `running`; a partial unique index (`one_active_job_idx`) enforces this at the DB level
- **Filter isolation:** `filter_bills()` joins `categories WHERE user_id = %s` — users cannot use each other's keyword sets
- **Session expiry:** 30 days; expired sessions require re-login

## Deployment (Render)

1. Push to GitHub
2. New Web Service → connect repo → Render uses `render.yaml` automatically
3. Set `LEGISCAN_API_KEY` in Render environment dashboard
4. After first deploy, run migration once via Render shell: `psql $DATABASE_URL < migrations/001_initial.sql`
