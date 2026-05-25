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

def _run_migrations():
    """Apply all migrations idempotently on startup (safe to re-run — all use IF NOT EXISTS)."""
    migration_files = [
        "migrations/001_initial.sql",
        "migrations/002_trigram_index.sql",
    ]
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            for path in migration_files:
                with open(path) as f:
                    cur.execute(f.read())


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_pool()
    _run_migrations()
    yield
    if database._pool is not None:
        database._pool.closeall()

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
