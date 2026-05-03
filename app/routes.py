"""HTTP routes for the helpdesk assistant."""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from . import ai
from .seed import maybe_seed
from .storage import TicketStore, parse_csv

bp = Blueprint("api", __name__, url_prefix="/api")


def _store() -> TicketStore:
    return current_app.extensions["ticket_store"]


@bp.after_request
def _no_cache(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@bp.get("/health")
def health():
    return {
        "ok": True,
        "ai_configured": bool(current_app.config.get("OPENAI_API_KEY")),
        "model": current_app.config.get("OPENAI_MODEL"),
    }


@bp.get("/tickets")
def list_tickets():
    return jsonify(_store().list())


@bp.get("/tickets/<ticket_id>")
def get_ticket(ticket_id: str):
    ticket = _store().get(ticket_id)
    if not ticket:
        return {"error": "not found"}, 404
    return jsonify(ticket)


@bp.post("/tickets")
def create_ticket():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    requester = payload.get("requester", "")
    if not subject and not body:
        return {"error": "subject or body required"}, 400
    ticket = _store().add(subject=subject, body=body, requester=requester)
    return jsonify(ticket), 201


@bp.post("/tickets/upload")
def upload_tickets():
    file = request.files.get("file")
    if not file:
        return {"error": "file required (multipart field 'file')"}, 400
    try:
        rows = parse_csv(file.read())
    except Exception as exc:  # noqa: BLE001
        return {"error": f"could not parse CSV: {exc}"}, 400
    if not rows:
        return {"error": "no usable rows in CSV"}, 400
    created = _store().bulk_add(rows)
    return jsonify({"created": len(created), "tickets": created}), 201


@bp.post("/tickets/<ticket_id>/analyze")
def analyze_ticket(ticket_id: str):
    """On-demand AI analysis. Triggered ONLY by the user's Generate click."""
    ticket = _store().get(ticket_id)
    if not ticket:
        return {"error": "not found"}, 404

    force_heuristic = bool((request.get_json(silent=True) or {}).get("offline"))
    api_key = "" if force_heuristic else current_app.config.get("OPENAI_API_KEY", "")
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    result = ai.analyze(ticket, api_key=api_key, model=model)
    updated = _store().update_ai(ticket_id, result)
    return jsonify(updated)


@bp.post("/tickets/<ticket_id>/status")
def set_status(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").lower()
    if status not in {"open", "in_progress", "resolved"}:
        return {"error": "invalid status"}, 400
    updated = _store().update_status(ticket_id, status)
    if not updated:
        return {"error": "not found"}, 404
    return jsonify(updated)


@bp.delete("/tickets/<ticket_id>")
def delete_ticket(ticket_id: str):
    if not _store().delete(ticket_id):
        return {"error": "not found"}, 404
    return {"ok": True}


@bp.post("/tickets/clear")
def clear_tickets():
    _store().clear()
    return {"ok": True}


@bp.post("/tickets/seed")
def seed_tickets():
    """Re-seed demo data. Useful on a public live demo after Clear all."""
    inserted = maybe_seed(_store())
    return {"ok": True, "inserted": inserted}


@bp.get("/stats")
def stats():
    return jsonify(_store().stats())
