import os
import psycopg2
import psycopg2.pool
from contextlib import contextmanager

_pool = None

def init_pool():
    global _pool
    if _pool is not None:
        return
    _pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=1,
        maxconn=10,
        dsn=os.environ["DATABASE_URL"],
    )

@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_pool() first")
    conn = _pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
