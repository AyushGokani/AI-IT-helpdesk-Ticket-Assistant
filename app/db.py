"""Database engine + ORM models.

- Production:  Postgres on Neon.tech (DATABASE_URL set as an env var on Render).
- Dev / tests: SQLite (file in DATA_DIR or per-test in tmp_path).

Tables auto-create on app boot (no Alembic for a small project).
``pool_pre_ping=True`` handles Neon's autosuspend/wake cycle cleanly — the
first request after idle recycles the stale connection instead of erroring.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


def _normalize_db_url(url: str) -> str:
    """Some providers hand out the legacy 'postgres://' scheme; SQLAlchemy 2.x
    requires 'postgresql://'. Normalize it transparently. Also make sure
    Neon URLs enforce SSL (they usually already do)."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    # Neon requires SSL. If the URL is plain Postgres and doesn't specify,
    # append sslmode=require so we don't get 'server does not support SSL'
    # style errors on connect. SQLite is left untouched.
    if url.startswith("postgresql://") and "sslmode=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    return url


def resolve_database_url(data_dir: Path) -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return _normalize_db_url(url)
    # Default: a local SQLite file alongside the JSON files we used to use.
    sqlite_path = data_dir / "triagent.sqlite3"
    return f"sqlite:///{sqlite_path}"


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", back_populates="user", cascade="all, delete-orphan"
    )


class PasswordResetCode(Base):
    """Short-lived 6-digit OTP for the forgot-password flow.

    We store a hash of the code (not the code itself) so a database
    leak doesn't enable account takeover. The plaintext is only ever
    in memory long enough to email it to the user.
    """

    __tablename__ = "password_reset_codes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    user: Mapped["User"] = relationship("User")


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requester: Mapped[str] = mapped_column(String(320), nullable=False, default="unknown@example.com")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    analyzed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ai: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="tickets")


# ---------------------------------------------------------------------------
# Engine + session factory
# ---------------------------------------------------------------------------

def make_engine(database_url: str):
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(
        database_url,
        echo=False,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
