"""HTTP routes for the helpdesk assistant. All ticket data is per-user."""

from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request

from . import ai
from .auth import login_required
from .seed import seed_for_user
from .storage import TicketStore, parse_csv

bp = Blueprint("api", __name__, url_prefix="/api")


def _store() -> TicketStore:
    return current_app.extensions["ticket_store"]


def _uid() -> str:
    return g.current_user["id"]


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
@login_required
def list_tickets():
    return jsonify(_store().list(_uid()))


@bp.get("/tickets/<ticket_id>")
@login_required
def get_ticket(ticket_id: str):
    ticket = _store().get(ticket_id, _uid())
    if not ticket:
        return {"error": "not found"}, 404
    return jsonify(ticket)


@bp.post("/tickets")
@login_required
def create_ticket():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject", "")
    body = payload.get("body", "")
    requester = payload.get("requester", "") or g.current_user["email"]
    if not subject and not body:
        return {"error": "subject or body required"}, 400
    ticket = _store().add(subject=subject, body=body, requester=requester, user_id=_uid())
    return jsonify(ticket), 201


@bp.post("/tickets/upload")
@login_required
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
    created = _store().bulk_add(rows, user_id=_uid())
    return jsonify({"created": len(created), "tickets": created}), 201


@bp.post("/tickets/<ticket_id>/analyze")
@login_required
def analyze_ticket(ticket_id: str):
    """On-demand AI analysis. Triggered ONLY by the user's Generate click."""
    ticket = _store().get(ticket_id, _uid())
    if not ticket:
        return {"error": "not found"}, 404

    force_heuristic = bool((request.get_json(silent=True) or {}).get("offline"))
    api_key = "" if force_heuristic else current_app.config.get("OPENAI_API_KEY", "")
    model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

    result = ai.analyze(ticket, api_key=api_key, model=model)
    updated = _store().update_ai(ticket_id, result, _uid())
    return jsonify(updated)


@bp.post("/tickets/<ticket_id>/status")
@login_required
def set_status(ticket_id: str):
    payload = request.get_json(silent=True) or {}
    status = (payload.get("status") or "").lower()
    if status not in {"open", "in_progress", "resolved"}:
        return {"error": "invalid status"}, 400
    updated = _store().update_status(ticket_id, status, _uid())
    if not updated:
        return {"error": "not found"}, 404
    return jsonify(updated)


@bp.delete("/tickets/<ticket_id>")
@login_required
def delete_ticket(ticket_id: str):
    if not _store().delete(ticket_id, _uid()):
        return {"error": "not found"}, 404
    return {"ok": True}


@bp.post("/tickets/clear")
@login_required
def clear_tickets():
    _store().clear(_uid())
    return {"ok": True}


@bp.post("/tickets/seed")
@login_required
def seed_tickets():
    """Re-seed demo data for the current user only."""
    inserted = seed_for_user(_store(), _uid())
    return {"ok": True, "inserted": inserted}


@bp.get("/stats")
@login_required
def stats():
    return jsonify(_store().stats(_uid()))
