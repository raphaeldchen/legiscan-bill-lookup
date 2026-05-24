import os
import psycopg
from contextlib import contextmanager

_pool = None

def init_pool():
    global _pool
    _pool = psycopg.connect(os.environ["DATABASE_URL"])

@contextmanager
def get_conn():
    conn = psycopg.connect(os.environ["DATABASE_URL"])
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
