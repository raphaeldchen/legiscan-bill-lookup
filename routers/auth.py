from fastapi import APIRouter, Response, HTTPException, Depends, Request
from models import SignupRequest, LoginRequest
from auth import hash_password, verify_password, create_session, get_current_user, delete_session
import database

router = APIRouter(prefix="/api/auth")

@router.post("/signup")
def signup(req: SignupRequest, response: Response):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (req.email,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")
            pw_hash = hash_password(req.password)
            cur.execute(
                "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
                (req.email, pw_hash),
            )
            row = cur.fetchone()
    user_id, email = row
    token = create_session(user_id)
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=30 * 24 * 3600
    )
    return {"id": user_id, "email": email}

@router.post("/login")
def login(req: LoginRequest, response: Response):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email, password_hash FROM users WHERE email = %s", (req.email,)
            )
            row = cur.fetchone()
    if not row or not verify_password(req.password, row[2]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_session(row[0])
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=30 * 24 * 3600
    )
    return {"id": row[0], "email": row[1]}

@router.post("/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        delete_session(token)
    response.delete_cookie("session")
    return {"ok": True}

@router.get("/me")
def me(user=Depends(get_current_user)):
    return user
