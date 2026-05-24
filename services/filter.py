from typing import List
import database


def _bill_row_to_dict(row) -> dict:
    return {
        "bill_id": row[0], "number": row[1], "title": row[2],
        "description": row[3], "status": row[4], "chamber": row[5],
        "committee": row[6], "sponsors": row[7],
        "last_action": row[8], "last_action_date": row[9],
    }


def _escape_like(kw: str) -> str:
    """Escape LIKE special chars so keywords are treated as literals in ILIKE.

    Uses '!' as the ESCAPE character (set in SQL via ESCAPE '!'):
      !% -> literal percent
      !_ -> literal underscore
      !! -> literal exclamation mark
    """
    return kw.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def filter_bills(category_ids: List[int], user_id: int, page: int = 1, limit: int = 50) -> dict:
    """
    Return bills whose description matches any keyword from the given categories.
    Only considers categories owned by user_id — prevents cross-user data access.
    Uses PostgreSQL ILIKE ANY ESCAPE '!' for case-insensitive, literal keyword matching.
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

    patterns = [f"%{_escape_like(kw)}%" for kw in keywords]
    offset = (page - 1) * limit

    # Generate individual ILIKE conditions so we can use ESCAPE '!' per expression.
    # PostgreSQL does not support ESCAPE with ILIKE ANY(array).
    ilike_clause = " OR ".join(["description ILIKE %s ESCAPE '!'" for _ in patterns])

    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT bill_id, number, title, description, status, chamber,
                   committee, sponsors, last_action, last_action_date
                   FROM bills WHERE ({ilike_clause})
                   ORDER BY last_action_date DESC LIMIT %s OFFSET %s""",
                (*patterns, limit, offset),
            )
            bills = cur.fetchall()
        with conn.cursor() as count_cur:
            count_cur.execute(
                f"SELECT COUNT(*) FROM bills WHERE ({ilike_clause})",
                patterns,
            )
            total = count_cur.fetchone()[0]

    return {"bills": [_bill_row_to_dict(b) for b in bills], "total": total, "page": page}
