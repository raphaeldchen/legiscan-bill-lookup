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
