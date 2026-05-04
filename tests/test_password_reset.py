"""Forgot-password / reset-with-code flow."""

from __future__ import annotations

import io
import re
from contextlib import redirect_stdout


def _signup(client, email="alice@example.com", password="supersecret"):
    res = client.post("/api/auth/signup", json={
        "email": email, "password": password, "name": "Alice",
    })
    assert res.status_code == 201
    return res.get_json()["user"]


def _request_code(client, email):
    """Trigger /forgot-password and capture the code from the console-backend
    output (the email_service falls back to printing the body)."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        res = client.post("/api/auth/forgot-password", json={"email": email})
    assert res.status_code == 200
    output = buf.getvalue()
    match = re.search(r"^\s*(\d{6})\s*$", output, re.MULTILINE)
    assert match, f"could not find code in console output: {output!r}"
    return match.group(1), output


def test_forgot_password_returns_generic_response_for_unknown_email(anon_client):
    res = anon_client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert res.status_code == 200
    assert "If an account exists" in res.get_json()["message"]


def test_forgot_password_sends_code_for_known_email(anon_client):
    _signup(anon_client)
    code, output = _request_code(anon_client, "alice@example.com")
    assert code.isdigit() and len(code) == 6
    assert "Triagent password reset" in output


def test_verify_reset_code_happy_path(anon_client):
    _signup(anon_client)
    code, _ = _request_code(anon_client, "alice@example.com")
    res = anon_client.post("/api/auth/verify-reset-code", json={
        "email": "alice@example.com", "code": code,
    })
    assert res.status_code == 200, res.get_json()


def test_verify_reset_code_rejects_wrong_code(anon_client):
    _signup(anon_client)
    _request_code(anon_client, "alice@example.com")
    res = anon_client.post("/api/auth/verify-reset-code", json={
        "email": "alice@example.com", "code": "000000",
    })
    assert res.status_code == 400
    assert "Invalid code" in res.get_json()["error"]


def test_reset_password_full_flow_logs_user_in(anon_client):
    _signup(anon_client)
    code, _ = _request_code(anon_client, "alice@example.com")

    res = anon_client.post("/api/auth/reset-password", json={
        "email": "alice@example.com",
        "code": code,
        "new_password": "brandnewpass123",
    })
    assert res.status_code == 200
    assert res.get_json()["user"]["email"] == "alice@example.com"

    # Session is set
    assert anon_client.get("/api/auth/me").get_json()["user"] is not None

    # Old password no longer works
    anon_client.post("/api/auth/logout")
    fail = anon_client.post("/api/auth/login", json={
        "email": "alice@example.com", "password": "supersecret",
    })
    assert fail.status_code == 401

    # New one does
    ok = anon_client.post("/api/auth/login", json={
        "email": "alice@example.com", "password": "brandnewpass123",
    })
    assert ok.status_code == 200


def test_reset_code_is_single_use(anon_client):
    _signup(anon_client)
    code, _ = _request_code(anon_client, "alice@example.com")

    first = anon_client.post("/api/auth/reset-password", json={
        "email": "alice@example.com", "code": code, "new_password": "brandnewpass123",
    })
    assert first.status_code == 200

    second = anon_client.post("/api/auth/reset-password", json={
        "email": "alice@example.com", "code": code, "new_password": "yetanotherpass",
    })
    assert second.status_code == 400


def test_reset_code_max_attempts(anon_client):
    _signup(anon_client)
    _request_code(anon_client, "alice@example.com")

    for _ in range(5):
        anon_client.post("/api/auth/verify-reset-code", json={
            "email": "alice@example.com", "code": "000000",
        })
    locked = anon_client.post("/api/auth/verify-reset-code", json={
        "email": "alice@example.com", "code": "000000",
    })
    assert locked.status_code == 400
    assert "Too many attempts" in locked.get_json()["error"]


def test_issuing_new_code_invalidates_old_one(anon_client):
    _signup(anon_client)
    code1, _ = _request_code(anon_client, "alice@example.com")
    code2, _ = _request_code(anon_client, "alice@example.com")
    assert code1 != code2

    # Old code no longer works
    res = anon_client.post("/api/auth/verify-reset-code", json={
        "email": "alice@example.com", "code": code1,
    })
    assert res.status_code == 400

    # New code works
    res = anon_client.post("/api/auth/verify-reset-code", json={
        "email": "alice@example.com", "code": code2,
    })
    assert res.status_code == 200


def test_reset_password_requires_min_length(anon_client):
    _signup(anon_client)
    code, _ = _request_code(anon_client, "alice@example.com")
    res = anon_client.post("/api/auth/reset-password", json={
        "email": "alice@example.com", "code": code, "new_password": "short",
    })
    assert res.status_code == 400
    assert "8 characters" in res.get_json()["error"]
