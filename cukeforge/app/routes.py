"""HTTP API for CukeForge."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from . import jira_client, pipeline

bp = Blueprint("api", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    jira_on = jira_client.jira_configured(
        current_app.config["JIRA_BASE_URL"],
        current_app.config["JIRA_EMAIL"],
        current_app.config["JIRA_API_TOKEN"],
    )
    from .ai import openai_available

    return jsonify(
        {
            "ok": True,
            "service": "cukeforge",
            "jira_mode": "live" if jira_on else "demo",
            "ai_mode": "openai"
            if openai_available(current_app.config["OPENAI_API_KEY"])
            else "heuristic",
        }
    )


@bp.get("/tickets")
def tickets():
    try:
        items, mode = jira_client.list_tickets(
            demo_path=current_app.config["DEMO_TICKETS_PATH"],
            base_url=current_app.config["JIRA_BASE_URL"],
            email=current_app.config["JIRA_EMAIL"],
            token=current_app.config["JIRA_API_TOKEN"],
            jql=current_app.config["JIRA_JQL"],
        )
        return jsonify({"mode": mode, "tickets": items})
    except Exception as exc:  # noqa: BLE001
        items, mode = jira_client.list_tickets(
            demo_path=current_app.config["DEMO_TICKETS_PATH"],
        )
        return jsonify(
            {
                "mode": "demo",
                "tickets": items,
                "warning": f"Jira unavailable ({exc}); showing demo tickets",
            }
        )


@bp.get("/tickets/<key>")
def ticket_detail(key: str):
    try:
        ticket = jira_client.get_ticket(
            key,
            demo_path=current_app.config["DEMO_TICKETS_PATH"],
            base_url=current_app.config["JIRA_BASE_URL"],
            email=current_app.config["JIRA_EMAIL"],
            token=current_app.config["JIRA_API_TOKEN"],
        )
        return jsonify(ticket)
    except KeyError:
        return jsonify({"error": f"Ticket {key} not found"}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502


@bp.post("/runs")
def create_run():
    body = request.get_json(silent=True) or {}
    ticket_key = (body.get("ticket_key") or "").strip()
    if not ticket_key:
        return jsonify({"error": "ticket_key is required"}), 400

    use_ai = body.get("use_ai", True)
    if isinstance(use_ai, str):
        use_ai = use_ai.lower() not in {"0", "false", "no", "off"}

    max_iterations = body.get("max_iterations")
    if max_iterations is None:
        max_iterations = current_app.config["CUKE_MAX_FIX_ITERATIONS"]
    try:
        max_iterations = int(max_iterations)
    except (TypeError, ValueError):
        max_iterations = current_app.config["CUKE_MAX_FIX_ITERATIONS"]

    ticket_override = body.get("ticket")
    if ticket_override is not None and not isinstance(ticket_override, dict):
        return jsonify({"error": "ticket must be an object"}), 400

    run = pipeline.execute_pipeline(
        ticket_key,
        demo_path=current_app.config["DEMO_TICKETS_PATH"],
        workspace_root=current_app.config["CUKE_WORKSPACE_ROOT"],
        api_key=current_app.config["OPENAI_API_KEY"],
        model=current_app.config["OPENAI_MODEL"],
        use_ai=bool(use_ai),
        max_iterations=max(1, min(max_iterations, 5)),
        jira_base_url=current_app.config["JIRA_BASE_URL"],
        jira_email=current_app.config["JIRA_EMAIL"],
        jira_token=current_app.config["JIRA_API_TOKEN"],
        ticket_override=ticket_override,
    )
    return jsonify(run.to_dict()), 200


@bp.get("/runs")
def runs():
    items = [r.to_dict() for r in pipeline.list_runs()]
    return jsonify({"runs": items})


@bp.get("/runs/<run_id>")
def run_detail(run_id: str):
    run = pipeline.get_run(run_id)
    if not run:
        return jsonify({"error": "Run not found"}), 404
    return jsonify(run.to_dict())
