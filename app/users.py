"""JSON-backed user store with password hashing.

Uses Werkzeug's PBKDF2 helpers (already a Flask dependency) — no extra
packages required, and stronger than a hand-rolled hash.
"""

from __future__ import annotations

import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from werkzeug.security import check_password_hash, generate_password_hash


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class AuthError(ValueError):
    """Raised for any signup/login validation failure."""


class UserStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write([])

    # ------------------------------------------------------------------ I/O

    def _read(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, users: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(users, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ API

    def create(self, email: str, password: str, name: str = "") -> dict[str, Any]:
        email = normalize_email(email)
        name = (name or "").strip()
        if not EMAIL_RE.match(email):
            raise AuthError("Please enter a valid email address.")
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters.")

        with self._lock:
            users = self._read()
            if any(u["email"] == email for u in users):
                raise AuthError("An account with that email already exists.")
            user = {
                "id": uuid.uuid4().hex[:12],
                "email": email,
                "name": name or email.split("@")[0].title(),
                "password_hash": generate_password_hash(password),
                "created_at": _now_iso(),
            }
            users.append(user)
            self._write(users)
        return self._public(user)

    def authenticate(self, email: str, password: str) -> dict[str, Any]:
        email = normalize_email(email)
        if not email or not password:
            raise AuthError("Email and password are required.")
        with self._lock:
            for u in self._read():
                if u["email"] == email and check_password_hash(u["password_hash"], password):
                    return self._public(u)
        raise AuthError("Invalid email or password.")

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._lock:
            for u in self._read():
                if u["id"] == user_id:
                    return self._public(u)
        return None

    def update_name(self, user_id: str, name: str) -> dict[str, Any] | None:
        name = (name or "").strip()
        if not name:
            raise AuthError("Name cannot be empty.")
        with self._lock:
            users = self._read()
            for u in users:
                if u["id"] == user_id:
                    u["name"] = name
                    self._write(users)
                    return self._public(u)
        return None

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        if len(new_password) < 8:
            raise AuthError("New password must be at least 8 characters.")
        with self._lock:
            users = self._read()
            for u in users:
                if u["id"] == user_id:
                    if not check_password_hash(u["password_hash"], old_password):
                        raise AuthError("Current password is incorrect.")
                    u["password_hash"] = generate_password_hash(new_password)
                    self._write(users)
                    return True
        raise AuthError("User not found.")

    def count(self) -> int:
        with self._lock:
            return len(self._read())

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _public(user: dict[str, Any]) -> dict[str, Any]:
        """Return a copy without the password hash."""
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "created_at": user.get("created_at"),
        }
