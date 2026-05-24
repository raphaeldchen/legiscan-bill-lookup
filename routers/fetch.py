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
