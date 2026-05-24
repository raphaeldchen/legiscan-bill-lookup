from unittest.mock import patch

def test_start_fetch_creates_job(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        r = client.post("/api/fetch")
    assert r.status_code == 200
    assert "job_id" in r.json()

def test_start_fetch_no_duplicate_while_queued(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        r1 = client.post("/api/fetch")
        r2 = client.post("/api/fetch")
    assert r1.json()["job_id"] == r2.json()["job_id"]

def test_fetch_status_returns_job(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        r = client.post("/api/fetch")
    job_id = r.json()["job_id"]
    r = client.get(f"/api/fetch/status/{job_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("queued", "running", "done", "failed")
    assert "bills_fetched" in data

def test_fetch_status_404_for_unknown(auth_client):
    client, _ = auth_client
    assert client.get("/api/fetch/status/99999").status_code == 404

def test_fetch_latest_none_when_no_jobs(auth_client):
    client, _ = auth_client
    r = client.get("/api/fetch/latest")
    assert r.status_code == 200
    assert r.json() is None

def test_fetch_latest_returns_most_recent(auth_client):
    client, _ = auth_client
    with patch("routers.fetch._run_sync"):
        client.post("/api/fetch")
    r = client.get("/api/fetch/latest")
    assert r.json() is not None
    assert "status" in r.json()

def test_fetch_requires_auth(client):
    assert client.post("/api/fetch").status_code == 401
