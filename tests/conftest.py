import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    # File-backed SQLite per test for clean isolation; in-memory would require
    # a shared connection trick across threads/sessions which isn't worth it.
    db_path = tmp_path / "test.sqlite3"
    app = create_app({
        "TESTING": True,
        "DATA_DIR": tmp_path,
        "OPENAI_API_KEY": "",
        "DATABASE_URL": f"sqlite:///{db_path}",
    })
    return app


@pytest.fixture()
def anon_client(app):
    """A client that hasn't logged in. Use this for auth-flow tests."""
    return app.test_client()


@pytest.fixture()
def client(app):
    """A client pre-authenticated as alice@example.com."""
    c = app.test_client()
    res = c.post("/api/auth/signup", json={
        "email": "alice@example.com",
        "password": "supersecret",
        "name": "Alice",
    })
    assert res.status_code == 201
    c._user = res.get_json()["user"]
    return c


@pytest.fixture()
def second_client(app):
    """A separate authenticated client for isolation tests."""
    c = app.test_client()
    res = c.post("/api/auth/signup", json={
        "email": "bob@example.com",
        "password": "supersecret",
        "name": "Bob",
    })
    assert res.status_code == 201
    c._user = res.get_json()["user"]
    return c
