"""Database engine + ORM models.

- Production:  Postgres (Render auto-injects DATABASE_URL).
- Dev / tests: SQLite (file in DATA_DIR or in-memory).

Tables auto-create on app boot (no Alembic for a small project).
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
    """Render still hands out the legacy 'postgres://' scheme; SQLAlchemy 2.x
    requires 'postgresql://'. Normalize it transparently."""
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
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
