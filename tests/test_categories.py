def test_create_category(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "Criminal Justice", "keywords": ["felony", "police"]})
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Criminal Justice"
    assert "felony" in data["keywords"]
    assert "id" in data

def test_list_categories(auth_client):
    client, _ = auth_client
    client.post("/api/categories", json={"name": "Cat A", "keywords": ["foo"]})
    client.post("/api/categories", json={"name": "Cat B", "keywords": ["bar"]})
    r = client.get("/api/categories")
    assert r.status_code == 200
    assert len(r.json()) == 2

def test_update_category_name(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "Old Name", "keywords": ["a"]})
    cat_id = r.json()["id"]
    r = client.put(f"/api/categories/{cat_id}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"
    assert r.json()["keywords"] == ["a"]   # keywords unchanged

def test_update_category_keywords(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "Cat", "keywords": ["old"]})
    cat_id = r.json()["id"]
    r = client.put(f"/api/categories/{cat_id}", json={"keywords": ["new1", "new2"]})
    assert r.status_code == 200
    assert r.json()["keywords"] == ["new1", "new2"]

def test_delete_category(auth_client):
    client, _ = auth_client
    r = client.post("/api/categories", json={"name": "To Delete", "keywords": []})
    cat_id = r.json()["id"]
    client.delete(f"/api/categories/{cat_id}")
    assert len(client.get("/api/categories").json()) == 0

def test_categories_isolated_per_user(client):
    client.post("/api/auth/signup", json={"email": "u1@test.com", "password": "pw"})
    client.post("/api/categories", json={"name": "U1 Cat", "keywords": []})
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "u2@test.com", "password": "pw"})
    assert len(client.get("/api/categories").json()) == 0

def test_delete_other_users_category_returns_404(client):
    client.post("/api/auth/signup", json={"email": "u1@test.com", "password": "pw"})
    r = client.post("/api/categories", json={"name": "U1 Cat", "keywords": []})
    cat_id = r.json()["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "u2@test.com", "password": "pw"})
    assert client.delete(f"/api/categories/{cat_id}").status_code == 404
