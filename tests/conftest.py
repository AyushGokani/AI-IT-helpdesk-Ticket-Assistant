import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.storage import TicketStore  # noqa: E402
from app.users import UserStore  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATA_DIR": tmp_path,
        "OPENAI_API_KEY": "",
    })
    app.extensions["ticket_store"] = TicketStore(tmp_path / "tickets.json")
    app.extensions["user_store"] = UserStore(tmp_path / "users.json")
    return app


@pytest.fixture()
def anon_client(app):
    """A client that hasn't logged in. Use this for auth-flow tests."""
    return app.test_client()


@pytest.fixture()
def client(app):
    """A client pre-authenticated as alice@example.com.

    All ticket/route tests use this so they don't need to handle auth boilerplate.
    """
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
