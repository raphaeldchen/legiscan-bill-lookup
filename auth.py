import bcrypt
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request, HTTPException
import database

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def generate_token() -> str:
    return secrets.token_hex(32)

def create_session(user_id: int) -> str:
    token = generate_token()
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (user_id, token, expires_at) VALUES (%s, %s, %s)",
                (user_id, token, expires),
            )
    return token

def delete_session(token: str) -> None:
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE token = %s", (token,))

def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT u.id, u.email FROM users u
                   JOIN sessions s ON s.user_id = u.id
                   WHERE s.token = %s AND s.expires_at > now()""",
                (token,),
            )
            row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"id": row[0], "email": row[1]}
