import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402


@pytest.fixture()
def app(tmp_path):
    app = create_app({
        "TESTING": True,
        "DATA_DIR": tmp_path,
        "OPENAI_API_KEY": "",
    })
    # Re-init store with the temp dir
    from app.storage import TicketStore
    app.extensions["ticket_store"] = TicketStore(tmp_path / "tickets.json")
    return app


@pytest.fixture()
def client(app):
    return app.test_client()
