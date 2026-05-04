"""SQLAlchemy-backed user store with password hashing.

Public API is unchanged from the original JSON-backed version, so the
auth blueprint and tests didn't need to change.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from .db import User


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


class AuthError(ValueError):
    """Raised for any signup/login validation failure."""


def _public(user: User) -> dict[str, Any]:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": user.created_at.isoformat(timespec="seconds") + "+00:00",
    }


class UserStore:
    def __init__(self, session_factory):
        self._SessionFactory = session_factory

    # ------------------------------------------------------------------ API

    def create(self, email: str, password: str, name: str = "") -> dict[str, Any]:
        email = normalize_email(email)
        name = (name or "").strip()
        if not EMAIL_RE.match(email):
            raise AuthError("Please enter a valid email address.")
        if len(password) < 8:
            raise AuthError("Password must be at least 8 characters.")

        with self._SessionFactory() as session:
            existing = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if existing is not None:
                raise AuthError("An account with that email already exists.")
            user = User(
                id=uuid.uuid4().hex[:12],
                email=email,
                name=name or email.split("@")[0].title(),
                password_hash=generate_password_hash(password),
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            return _public(user)

    def authenticate(self, email: str, password: str) -> dict[str, Any]:
        email = normalize_email(email)
        if not email or not password:
            raise AuthError("Email and password are required.")
        with self._SessionFactory() as session:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user is not None and check_password_hash(user.password_hash, password):
                return _public(user)
        raise AuthError("Invalid email or password.")

    def get(self, user_id: str) -> dict[str, Any] | None:
        with self._SessionFactory() as session:
            user = session.get(User, user_id)
            return _public(user) if user else None

    def update_name(self, user_id: str, name: str) -> dict[str, Any] | None:
        name = (name or "").strip()
        if not name:
            raise AuthError("Name cannot be empty.")
        with self._SessionFactory() as session:
            user = session.get(User, user_id)
            if user is None:
                return None
            user.name = name
            session.commit()
            session.refresh(user)
            return _public(user)

    def change_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        if len(new_password) < 8:
            raise AuthError("New password must be at least 8 characters.")
        with self._SessionFactory() as session:
            user = session.get(User, user_id)
            if user is None:
                raise AuthError("User not found.")
            if not check_password_hash(user.password_hash, old_password):
                raise AuthError("Current password is incorrect.")
            user.password_hash = generate_password_hash(new_password)
            session.commit()
            return True

    def count(self) -> int:
        with self._SessionFactory() as session:
            return session.query(User).count()
