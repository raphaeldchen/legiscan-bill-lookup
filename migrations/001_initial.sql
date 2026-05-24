CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
