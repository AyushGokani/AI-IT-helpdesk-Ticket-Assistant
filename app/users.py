"""SQLAlchemy-backed user store with password hashing.

Public API is unchanged from the original JSON-backed version, so the
auth blueprint and tests didn't need to change.
"""

from __future__ import annotations

import re
import secrets
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from .db import PasswordResetCode, User, utcnow


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

    # ---------------------------------------------------------- password reset

    RESET_CODE_TTL = timedelta(minutes=15)
    RESET_CODE_MAX_ATTEMPTS = 5

    def get_by_email(self, email: str) -> dict[str, Any] | None:
        email = normalize_email(email)
        with self._SessionFactory() as session:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            return _public(user) if user else None

    def issue_reset_code(self, email: str) -> tuple[dict[str, Any], str] | None:
        """Generate a fresh 6-digit code, persist its hash, and return
        ``(public_user, plaintext_code)``. Returns ``None`` if no such user.

        Any prior unused codes for this user are invalidated so only the
        latest one can succeed.
        """
        email = normalize_email(email)
        with self._SessionFactory() as session:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user is None:
                return None
            # Invalidate any pending codes for this user
            for old in session.execute(
                select(PasswordResetCode).where(
                    PasswordResetCode.user_id == user.id,
                    PasswordResetCode.used_at.is_(None),
                )
            ).scalars().all():
                old.used_at = utcnow()

            code = f"{secrets.randbelow(1_000_000):06d}"
            entry = PasswordResetCode(
                id=uuid.uuid4().hex[:12],
                user_id=user.id,
                code_hash=generate_password_hash(code),
                expires_at=utcnow() + self.RESET_CODE_TTL,
            )
            session.add(entry)
            session.commit()
            return _public(user), code

    def verify_reset_code(self, email: str, code: str) -> str | None:
        """Verify a reset code without consuming it (used by the 'verify'
        step before showing the new-password form). Returns the
        reset-record id on success, None on failure.
        """
        email = normalize_email(email)
        code = (code or "").strip()
        if not code.isdigit() or len(code) != 6:
            raise AuthError("Enter the 6-digit code from your email.")

        with self._SessionFactory() as session:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user is None:
                raise AuthError("Invalid or expired code.")
            entry = session.execute(
                select(PasswordResetCode).where(
                    PasswordResetCode.user_id == user.id,
                    PasswordResetCode.used_at.is_(None),
                ).order_by(PasswordResetCode.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            if entry is None or entry.expires_at < utcnow():
                raise AuthError("Invalid or expired code.")
            if entry.attempts >= self.RESET_CODE_MAX_ATTEMPTS:
                raise AuthError("Too many attempts. Request a new code.")
            entry.attempts += 1
            valid = check_password_hash(entry.code_hash, code)
            session.commit()
            if not valid:
                remaining = self.RESET_CODE_MAX_ATTEMPTS - entry.attempts
                if remaining <= 0:
                    raise AuthError("Too many attempts. Request a new code.")
                raise AuthError(f"Invalid code. {remaining} attempt(s) left.")
            return entry.id

    def consume_reset_code(self, email: str, code: str, new_password: str) -> dict[str, Any]:
        """Verify the code and atomically reset the password."""
        if len(new_password) < 8:
            raise AuthError("New password must be at least 8 characters.")
        email = normalize_email(email)
        code = (code or "").strip()
        if not code.isdigit() or len(code) != 6:
            raise AuthError("Enter the 6-digit code from your email.")

        with self._SessionFactory() as session:
            user = session.execute(select(User).where(User.email == email)).scalar_one_or_none()
            if user is None:
                raise AuthError("Invalid or expired code.")
            entry = session.execute(
                select(PasswordResetCode).where(
                    PasswordResetCode.user_id == user.id,
                    PasswordResetCode.used_at.is_(None),
                ).order_by(PasswordResetCode.created_at.desc()).limit(1)
            ).scalar_one_or_none()
            if entry is None or entry.expires_at < utcnow():
                raise AuthError("Invalid or expired code.")
            if entry.attempts >= self.RESET_CODE_MAX_ATTEMPTS:
                raise AuthError("Too many attempts. Request a new code.")
            entry.attempts += 1
            if not check_password_hash(entry.code_hash, code):
                session.commit()
                remaining = self.RESET_CODE_MAX_ATTEMPTS - entry.attempts
                if remaining <= 0:
                    raise AuthError("Too many attempts. Request a new code.")
                raise AuthError(f"Invalid code. {remaining} attempt(s) left.")

            user.password_hash = generate_password_hash(new_password)
            entry.used_at = utcnow()
            session.commit()
            return _public(user)
