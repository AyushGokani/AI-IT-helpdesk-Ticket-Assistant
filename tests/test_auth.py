def test_signup_creates_session_and_returns_user(anon_client):
    res = anon_client.post("/api/auth/signup", json={
        "email": "Carol@Example.com",
        "password": "supersecret",
        "name": "Carol",
    })
    assert res.status_code == 201
    user = res.get_json()["user"]
    assert user["email"] == "carol@example.com"  # normalized
    assert user["name"] == "Carol"
    assert "password_hash" not in user

    me = anon_client.get("/api/auth/me").get_json()
    assert me["user"]["email"] == "carol@example.com"


def test_signup_rejects_short_password(anon_client):
    res = anon_client.post("/api/auth/signup", json={
        "email": "x@y.com", "password": "abc",
    })
    assert res.status_code == 400
    assert "8 characters" in res.get_json()["error"]


def test_signup_rejects_invalid_email(anon_client):
    res = anon_client.post("/api/auth/signup", json={
        "email": "not-an-email", "password": "supersecret",
    })
    assert res.status_code == 400


def test_signup_rejects_duplicate_email(anon_client):
    anon_client.post("/api/auth/signup", json={"email": "dup@x.com", "password": "supersecret"})
    res = anon_client.post("/api/auth/signup", json={"email": "dup@x.com", "password": "supersecret"})
    assert res.status_code == 400
    assert "already exists" in res.get_json()["error"]


def test_login_requires_correct_password(anon_client):
    anon_client.post("/api/auth/signup", json={"email": "u@x.com", "password": "supersecret"})
    anon_client.post("/api/auth/logout")

    bad = anon_client.post("/api/auth/login", json={"email": "u@x.com", "password": "wrong"})
    assert bad.status_code == 401

    good = anon_client.post("/api/auth/login", json={"email": "u@x.com", "password": "supersecret"})
    assert good.status_code == 200
    assert good.get_json()["user"]["email"] == "u@x.com"


def test_logout_clears_session(client):
    assert client.get("/api/auth/me").get_json()["user"] is not None
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").get_json()["user"] is None


def test_protected_routes_require_auth(anon_client):
    for path in ["/api/tickets", "/api/stats"]:
        res = anon_client.get(path)
        assert res.status_code == 401, f"{path} should require auth"


def test_change_password_requires_current(client):
    bad = client.post("/api/auth/change-password", json={
        "current_password": "wrong", "new_password": "newstrongpw",
    })
    assert bad.status_code == 400

    good = client.post("/api/auth/change-password", json={
        "current_password": "supersecret", "new_password": "newstrongpw",
    })
    assert good.status_code == 200

    # Old password no longer works
    client.post("/api/auth/logout")
    fail = client.post("/api/auth/login", json={
        "email": "alice@example.com", "password": "supersecret",
    })
    assert fail.status_code == 401
    ok = client.post("/api/auth/login", json={
        "email": "alice@example.com", "password": "newstrongpw",
    })
    assert ok.status_code == 200


def test_update_name(client):
    res = client.patch("/api/auth/me", json={"name": "Alice Cooper"})
    assert res.status_code == 200
    assert res.get_json()["user"]["name"] == "Alice Cooper"


def test_tickets_are_per_user(client, second_client):
    client.post("/api/tickets", json={"subject": "alice ticket", "body": "x"})
    second_client.post("/api/tickets", json={"subject": "bob ticket", "body": "y"})

    a = client.get("/api/tickets").get_json()
    b = second_client.get("/api/tickets").get_json()
    assert len(a) == 1 and a[0]["subject"] == "alice ticket"
    assert len(b) == 1 and b[0]["subject"] == "bob ticket"

    # Cross-account access is a 404 (we don't even leak existence)
    bob_id = b[0]["id"]
    assert client.get(f"/api/tickets/{bob_id}").status_code == 404
    assert client.delete(f"/api/tickets/{bob_id}").status_code == 404
