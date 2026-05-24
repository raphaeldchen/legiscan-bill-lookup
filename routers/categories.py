from fastapi import APIRouter, Depends, HTTPException
from models import CategoryCreate, CategoryUpdate
from auth import get_current_user
import database

router = APIRouter(prefix="/api/categories")

@router.get("")
def list_categories(user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, keywords FROM categories WHERE user_id = %s ORDER BY created_at",
                (user["id"],),
            )
            rows = cur.fetchall()
    return [{"id": r[0], "name": r[1], "keywords": r[2]} for r in rows]

@router.post("")
def create_category(req: CategoryCreate, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO categories (user_id, name, keywords) VALUES (%s, %s, %s) "
                "RETURNING id, name, keywords",
                (user["id"], req.name, req.keywords),
            )
            row = cur.fetchone()
    return {"id": row[0], "name": row[1], "keywords": row[2]}

@router.put("/{category_id}")
def update_category(category_id: int, req: CategoryUpdate, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM categories WHERE id = %s AND user_id = %s",
                (category_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")

            set_parts = ["updated_at = now()"]
            values = []
            if req.name is not None:
                set_parts.append("name = %s")
                values.append(req.name)
            if req.keywords is not None:
                set_parts.append("keywords = %s")
                values.append(req.keywords)
            values.append(category_id)

            cur.execute(
                f"UPDATE categories SET {', '.join(set_parts)} WHERE id = %s "
                "RETURNING id, name, keywords",
                values,
            )
            row = cur.fetchone()
    return {"id": row[0], "name": row[1], "keywords": row[2]}

@router.delete("/{category_id}")
def delete_category(category_id: int, user=Depends(get_current_user)):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM categories WHERE id = %s AND user_id = %s RETURNING id",
                (category_id, user["id"]),
            )
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="Category not found")
    return {"ok": True}
