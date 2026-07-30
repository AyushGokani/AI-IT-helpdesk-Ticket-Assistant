"""CukeForge — AI that turns Jira tickets into passing Cucumber (Behave) tests."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask


def create_app() -> Flask:
    root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__,
        static_folder=str(root / "frontend"),
        static_url_path="",
    )
    app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY", "dev-secret")
    app.config["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY", "").strip()
    app.config["OPENAI_MODEL"] = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    app.config["JIRA_BASE_URL"] = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    app.config["JIRA_EMAIL"] = os.environ.get("JIRA_EMAIL", "").strip()
    app.config["JIRA_API_TOKEN"] = os.environ.get("JIRA_API_TOKEN", "").strip()
    app.config["JIRA_JQL"] = os.environ.get(
        "JIRA_JQL", "project = DEMO ORDER BY updated DESC"
    )
    app.config["CUKE_MAX_FIX_ITERATIONS"] = int(
        os.environ.get("CUKE_MAX_FIX_ITERATIONS", "3")
    )
    workspace_root = Path(
        os.environ.get("CUKE_WORKSPACE_ROOT", str(root / "workspaces"))
    )
    if not workspace_root.is_absolute():
        workspace_root = root / workspace_root
    app.config["CUKE_WORKSPACE_ROOT"] = workspace_root
    app.config["DEMO_TICKETS_PATH"] = root / "samples" / "demo_tickets.json"

    from .routes import bp

    app.register_blueprint(bp)

    @app.route("/")
    def index():
        return app.send_static_file("index.html")

    return app
