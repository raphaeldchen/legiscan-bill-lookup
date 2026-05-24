import csv
import io
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from auth import get_current_user
from models import FilterRequest
from services.filter import filter_bills, _bill_row_to_dict
import database

router = APIRouter(prefix="/api/bills")

# Hard cap on CSV export rows to keep response sizes bounded (~6K IL bills fits well below this)
_EXPORT_LIMIT = 100_000

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
        bills = filter_bills(ids, user["id"], page=1, limit=_EXPORT_LIMIT)["bills"]
    else:
        with database.get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT bill_id, number, title, description, status, chamber,
                       committee, sponsors, last_action, last_action_date
                       FROM bills ORDER BY last_action_date DESC LIMIT %s""",
                    (_EXPORT_LIMIT,),
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
