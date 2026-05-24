import json
import database

def _insert_bill(bill_id: str, description: str, last_action_date: str = "2025-01-01"):
    with database.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bills (bill_id, number, title, description, status,
                   chamber, committee, sponsors, last_action, last_action_date, raw_json)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (bill_id, f"HB {bill_id}", f"Title {bill_id}", description,
                 "1", "House", "", "", "", last_action_date, json.dumps({})),
            )

def test_list_bills_empty(auth_client):
    client, _ = auth_client
    r = client.get("/api/bills")
    assert r.status_code == 200
    assert r.json() == {"bills": [], "total": 0, "page": 1}

def test_list_bills_returns_all(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A bill about felony")
    _insert_bill("2", "A bill about schools")
    assert client.get("/api/bills").json()["total"] == 2

def test_list_bills_pagination(auth_client):
    client, _ = auth_client
    for i in range(5):
        _insert_bill(str(i), f"Bill {i}")
    assert len(client.get("/api/bills?page=1&limit=3").json()["bills"]) == 3
    assert len(client.get("/api/bills?page=2&limit=3").json()["bills"]) == 2

def test_filter_bills_by_keyword(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A bill about felony charges")
    _insert_bill("2", "A bill about school funding")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    cat_id = r.json()["id"]
    data = client.post("/api/bills/filter", json={"category_ids": [cat_id]}).json()
    assert data["total"] == 1
    assert data["bills"][0]["bill_id"] == "1"

def test_filter_case_insensitive(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A bill about FELONY charges")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    cat_id = r.json()["id"]
    assert client.post("/api/bills/filter", json={"category_ids": [cat_id]}).json()["total"] == 1

def test_filter_empty_keywords_returns_empty(auth_client):
    client, _ = auth_client
    _insert_bill("1", "Any bill")
    r = client.post("/api/categories", json={"name": "Empty", "keywords": []})
    cat_id = r.json()["id"]
    assert client.post("/api/bills/filter", json={"category_ids": [cat_id]}).json()["bills"] == []

def test_filter_multiple_categories(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A felony bill")
    _insert_bill("2", "An energy bill")
    _insert_bill("3", "An unrelated bill")
    r1 = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    r2 = client.post("/api/categories", json={"name": "Energy", "keywords": ["energy"]})
    data = client.post("/api/bills/filter", json={"category_ids": [r1.json()["id"], r2.json()["id"]]}).json()
    assert data["total"] == 2

def test_filter_cannot_use_other_users_category(client):
    client.post("/api/auth/signup", json={"email": "u1@test.com", "password": "pw"})
    _insert_bill("1", "A felony bill")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    u1_cat_id = r.json()["id"]
    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "u2@test.com", "password": "pw"})
    assert client.post("/api/bills/filter", json={"category_ids": [u1_cat_id]}).json()["total"] == 0

def test_export_csv_includes_header(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A felony bill")
    r = client.get("/api/bills/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "bill_id" in r.text
    assert "1" in r.text

def test_export_csv_filtered_by_category(auth_client):
    client, _ = auth_client
    _insert_bill("1", "A felony bill")
    _insert_bill("2", "An unrelated bill")
    r = client.post("/api/categories", json={"name": "Criminal", "keywords": ["felony"]})
    cat_id = r.json()["id"]
    resp = client.get(f"/api/bills/export?category_ids={cat_id}")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "felony" in resp.text
    assert "unrelated" not in resp.text

def test_bills_require_auth(client):
    assert client.get("/api/bills").status_code == 401
