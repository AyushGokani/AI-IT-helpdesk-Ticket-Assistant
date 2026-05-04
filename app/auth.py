"""Session-based auth: signup / login / logout / me + login_required."""

from __future__ import annotations

from functools import wraps

from flask import Blueprint, current_app, g, jsonify, request, session

from .email_service import send_password_reset_code
from .users import AuthError, UserStore


bp = Blueprint("auth", __name__, url_prefix="/api/auth")

SESSION_USER_KEY = "user_id"


def _users() -> UserStore:
    return current_app.extensions["user_store"]


def _current_user() -> dict | None:
    user_id = session.get(SESSION_USER_KEY)
    if not user_id:
        return None
    cached = getattr(g, "_current_user", None)
    if cached is not None and cached["id"] == user_id:
        return cached
    user = _users().get(user_id)
    g._current_user = user
    return user


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = _current_user()
        if not user:
            return jsonify({"error": "authentication required"}), 401
        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@bp.post("/signup")
def signup():
    payload = request.get_json(silent=True) or {}
    try:
        user = _users().create(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            name=payload.get("name", ""),
        )
    except AuthError as exc:
        return {"error": str(exc)}, 400
    session.clear()
    session[SESSION_USER_KEY] = user["id"]
    session.permanent = True

    # Optionally seed the new account with demo tickets so their first login
    # isn't a blank slate. Triggered at signup, *not* per-request, to keep the
    # AI on-demand promise.
    if current_app.config.get("SEED_DEMO_DATA"):
        from .seed import seed_for_user
        seed_for_user(current_app.extensions["ticket_store"], user["id"])

    return jsonify({"user": user}), 201


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    try:
        user = _users().authenticate(payload.get("email", ""), payload.get("password", ""))
    except AuthError as exc:
        return {"error": str(exc)}, 401
    session.clear()
    session[SESSION_USER_KEY] = user["id"]
    session.permanent = True
    return jsonify({"user": user})


@bp.post("/logout")
def logout():
    session.clear()
    return {"ok": True}


@bp.get("/me")
def me():
    user = _current_user()
    if not user:
        return {"user": None}
    return {"user": user}


@bp.patch("/me")
@login_required
def update_me():
    payload = request.get_json(silent=True) or {}
    name = payload.get("name")
    if name is not None:
        try:
            updated = _users().update_name(g.current_user["id"], name)
        except AuthError as exc:
            return {"error": str(exc)}, 400
        return {"user": updated}
    return {"user": g.current_user}


@bp.post("/change-password")
@login_required
def change_password():
    payload = request.get_json(silent=True) or {}
    try:
        _users().change_password(
            g.current_user["id"],
            payload.get("current_password", ""),
            payload.get("new_password", ""),
        )
    except AuthError as exc:
        return {"error": str(exc)}, 400
    return {"ok": True}


# ---------------------------------------------------------------------------
# Forgot-password flow
#
# Three steps from the client's POV:
#   1. POST /forgot-password           {email}            → send code by email
#   2. POST /verify-reset-code         {email, code}      → validate code (does not consume)
#   3. POST /reset-password            {email, code,
#                                       new_password}     → set new password
#
# We always return a generic success response from /forgot-password so the
# endpoint can't be used to enumerate which emails have accounts.
# ---------------------------------------------------------------------------

_FORGOT_RESPONSE = {
    "ok": True,
    "message": "If an account exists for that email, a 6-digit code has been sent.",
}


@bp.post("/forgot-password")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    email = payload.get("email", "")
    issued = _users().issue_reset_code(email)
    if issued is not None:
        user, code = issued
        try:
            send_password_reset_code(to=user["email"], name=user["name"], code=code)
        except Exception:  # noqa: BLE001
            current_app.logger.exception("password reset email failed for %s", email)
            # Don't leak the failure to the client — they shouldn't know
            # whether the email step succeeded.
    return _FORGOT_RESPONSE


@bp.post("/verify-reset-code")
def verify_reset_code():
    payload = request.get_json(silent=True) or {}
    try:
        _users().verify_reset_code(payload.get("email", ""), payload.get("code", ""))
    except AuthError as exc:
        return {"error": str(exc)}, 400
    return {"ok": True}


@bp.post("/reset-password")
def reset_password():
    payload = request.get_json(silent=True) or {}
    try:
        user = _users().consume_reset_code(
            payload.get("email", ""),
            payload.get("code", ""),
            payload.get("new_password", ""),
        )
    except AuthError as exc:
        return {"error": str(exc)}, 400
    # Auto-login on success
    session.clear()
    session[SESSION_USER_KEY] = user["id"]
    session.permanent = True
    return jsonify({"user": user})
