"""AI Helpdesk Ticket Assistant - Flask application factory."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask

from .seed import maybe_seed
from .storage import TicketStore


def create_app(test_config: dict | None = None) -> Flask:
    load_dotenv()

    app = Flask(
        __name__,
        static_folder="../frontend",
        static_url_path="",
    )
    default_data_dir = Path(__file__).resolve().parent.parent / "data"
    app.config.update(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "dev-secret-key"),
        OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", ""),
        OPENAI_MODEL=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        DATA_DIR=Path(os.getenv("DATA_DIR") or default_data_dir),
        SEED_DEMO_DATA=os.getenv("SEED_DEMO_DATA", "0") == "1",
    )
    if test_config:
        app.config.update(test_config)

    app.config["DATA_DIR"].mkdir(parents=True, exist_ok=True)

    store = TicketStore(app.config["DATA_DIR"] / "tickets.json")
    app.extensions["ticket_store"] = store

    if app.config["SEED_DEMO_DATA"]:
        maybe_seed(store)

    from .routes import bp as api_bp

    app.register_blueprint(api_bp)

    @app.route("/")
    def index():  # pragma: no cover - thin wrapper
        return app.send_static_file("index.html")

    return app
