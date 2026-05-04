import io


def test_health_is_public(anon_client):
    res = anon_client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["ok"] is True
    assert body["ai_configured"] is False


def test_create_list_and_get(client):
    res = client.post("/api/tickets", json={
        "subject": "VPN broken",
        "body": "VPN keeps disconnecting, urgent",
        "requester": "alex@acme.com",
    })
    assert res.status_code == 201
    ticket = res.get_json()
    assert ticket["id"]
    assert ticket["status"] == "open"
    assert ticket["ai"] is None

    res = client.get("/api/tickets")
    assert res.status_code == 200
    assert any(t["id"] == ticket["id"] for t in res.get_json())

    res = client.get(f"/api/tickets/{ticket['id']}")
    assert res.status_code == 200
    assert res.get_json()["subject"] == "VPN broken"


def test_create_requires_content(client):
    res = client.post("/api/tickets", json={})
    assert res.status_code == 400


def test_analyze_uses_heuristic_and_persists(client):
    res = client.post("/api/tickets", json={
        "subject": "Wi-Fi outage",
        "body": "All users on floor 3 lost wifi, urgent",
        "requester": "noc@acme.com",
    })
    ticket = res.get_json()

    res = client.post(f"/api/tickets/{ticket['id']}/analyze", json={})
    assert res.status_code == 200
    updated = res.get_json()
    assert updated["ai"]["category"] == "network"
    assert updated["ai"]["priority"] == "urgent"
    assert updated["ai"]["source"] == "heuristic"
    assert "reply_draft" in updated["ai"]
    assert "analyzed_at" in updated

    # Re-fetch to confirm persistence
    res = client.get(f"/api/tickets/{ticket['id']}")
    assert res.get_json()["ai"]["category"] == "network"


def test_analyze_offline_flag_skips_llm(client, app, monkeypatch):
    from app import ai as ai_mod

    called = {"n": 0}

    def boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("LLM should not be called when offline=True")

    monkeypatch.setattr(ai_mod, "llm_classify", boom)
    app.config["OPENAI_API_KEY"] = "sk-fake"

    res = client.post("/api/tickets", json={
        "subject": "Password reset",
        "body": "Locked out of Okta",
        "requester": "u@acme.com",
    })
    ticket = res.get_json()

    res = client.post(f"/api/tickets/{ticket['id']}/analyze", json={"offline": True})
    assert res.status_code == 200
    assert res.get_json()["ai"]["source"] == "heuristic"
    assert called["n"] == 0


def test_status_and_delete(client):
    res = client.post("/api/tickets", json={"subject": "x", "body": "y", "requester": "u@a.com"})
    tid = res.get_json()["id"]

    res = client.post(f"/api/tickets/{tid}/status", json={"status": "resolved"})
    assert res.status_code == 200
    assert res.get_json()["status"] == "resolved"

    res = client.post(f"/api/tickets/{tid}/status", json={"status": "bogus"})
    assert res.status_code == 400

    res = client.delete(f"/api/tickets/{tid}")
    assert res.status_code == 200
    res = client.get(f"/api/tickets/{tid}")
    assert res.status_code == 404


def test_csv_upload_and_stats(client):
    csv_bytes = (
        b"subject,body,requester\n"
        b"VPN down,VPN dropping,alex@acme.com\n"
        b"Locked out,Need password reset,priya@acme.com\n"
    )
    data = {"file": (io.BytesIO(csv_bytes), "tickets.csv")}
    res = client.post("/api/tickets/upload", data=data, content_type="multipart/form-data")
    assert res.status_code == 201
    body = res.get_json()
    assert body["created"] == 2

    res = client.get("/api/stats")
    stats = res.get_json()
    assert stats["total"] == 2
    assert stats["analyzed"] == 0
    assert stats["open"] == 2


def test_csv_upload_requires_file(client):
    res = client.post("/api/tickets/upload", data={}, content_type="multipart/form-data")
    assert res.status_code == 400


def test_clear(client):
    client.post("/api/tickets", json={"subject": "a", "body": "b"})
    client.post("/api/tickets/clear")
    assert client.get("/api/tickets").get_json() == []


def test_seed_endpoint_only_populates_when_user_is_empty(client):
    # Wipe alice's slate (signup may have seeded if SEED_DEMO_DATA was on)
    client.post("/api/tickets/clear")
    res = client.post("/api/tickets/seed")
    body = res.get_json()
    assert body["ok"] is True
    assert body["inserted"] >= 1
    first = body["inserted"]

    # Second call is a no-op since the user already has tickets
    res = client.post("/api/tickets/seed")
    assert res.get_json()["inserted"] == 0

    # Sanity: the previously-seeded count is still there
    assert len(client.get("/api/tickets").get_json()) == first


def test_no_cache_headers_on_api(client):
    res = client.get("/api/tickets")
    assert "no-store" in res.headers.get("Cache-Control", "")
