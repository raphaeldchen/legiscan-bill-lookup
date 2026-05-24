def test_signup(client):
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123"})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == "a@b.com"
    assert "id" in data
    assert "session" in r.cookies

def test_signup_duplicate_email(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw"})
    r = client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw"})
    assert r.status_code == 400

def test_login(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "pw123"})
    assert r.status_code == 200
    assert "session" in r.cookies

def test_login_wrong_password(client):
    client.post("/api/auth/signup", json={"email": "a@b.com", "password": "pw123"})
    r = client.post("/api/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert r.status_code == 401

def test_me_requires_auth(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401

def test_me_returns_user(auth_client):
    client, user = auth_client
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "intern@test.com"

def test_logout_clears_session(auth_client):
    client, _ = auth_client
    client.post("/api/auth/logout")
    r = client.get("/api/auth/me")
    assert r.status_code == 401
