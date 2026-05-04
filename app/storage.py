"""SQLAlchemy-backed ticket store. CSV parser stays as a free function."""

from __future__ import annotations

import csv
import io
import uuid
from typing import Any, Iterable

from sqlalchemy import select

from .db import Ticket


def _serialize(ticket: Ticket) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": ticket.id,
        "user_id": ticket.user_id,
        "subject": ticket.subject,
        "body": ticket.body,
        "requester": ticket.requester,
        "status": ticket.status,
        "created_at": ticket.created_at.isoformat(timespec="seconds") + "+00:00",
        "ai": ticket.ai,
    }
    if ticket.analyzed_at is not None:
        out["analyzed_at"] = ticket.analyzed_at.isoformat(timespec="seconds") + "+00:00"
    return out


def _new_id() -> str:
    return uuid.uuid4().hex[:10]


class TicketStore:
    def __init__(self, session_factory):
        self._SessionFactory = session_factory

    def _ownership_filter(self, query, user_id: str | None):
        if user_id is None:
            return query
        return query.where(Ticket.user_id == user_id)

    # ------------------------------------------------------------------ READ

    def list(self, user_id: str | None = None) -> list[dict[str, Any]]:
        with self._SessionFactory() as session:
            stmt = self._ownership_filter(select(Ticket), user_id).order_by(Ticket.created_at.desc())
            return [_serialize(t) for t in session.execute(stmt).scalars().all()]

    def get(self, ticket_id: str, user_id: str | None = None) -> dict[str, Any] | None:
        with self._SessionFactory() as session:
            ticket = session.get(Ticket, ticket_id)
            if ticket is None:
                return None
            if user_id is not None and ticket.user_id != user_id:
                return None
            return _serialize(ticket)

    def stats(self, user_id: str | None = None) -> dict[str, Any]:
        tickets = self.list(user_id)
        by_category: dict[str, int] = {}
        by_priority: dict[str, int] = {}
        analyzed = 0
        for t in tickets:
            ai = t.get("ai") or {}
            if ai:
                analyzed += 1
                cat = ai.get("category", "uncategorized")
                pri = ai.get("priority", "unknown")
                by_category[cat] = by_category.get(cat, 0) + 1
                by_priority[pri] = by_priority.get(pri, 0) + 1
        return {
            "total": len(tickets),
            "analyzed": analyzed,
            "open": sum(1 for t in tickets if t.get("status") == "open"),
            "resolved": sum(1 for t in tickets if t.get("status") == "resolved"),
            "by_category": by_category,
            "by_priority": by_priority,
        }

    # ----------------------------------------------------------------- WRITE

    def add(
        self,
        subject: str,
        body: str,
        requester: str | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        with self._SessionFactory() as session:
            ticket = Ticket(
                id=_new_id(),
                user_id=user_id,
                subject=(subject or "").strip() or "(no subject)",
                body=(body or "").strip(),
                requester=(requester or "").strip() or "unknown@example.com",
                status="open",
            )
            session.add(ticket)
            session.commit()
            session.refresh(ticket)
            return _serialize(ticket)

    def bulk_add(
        self,
        rows: Iterable[dict[str, str]],
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        with self._SessionFactory() as session:
            for row in rows:
                ticket = Ticket(
                    id=_new_id(),
                    user_id=user_id,
                    subject=(row.get("subject") or "").strip() or "(no subject)",
                    body=(row.get("body") or row.get("description") or "").strip(),
                    requester=(row.get("requester") or row.get("email") or "unknown@example.com").strip(),
                    status="open",
                )
                session.add(ticket)
                created.append(ticket)
            session.commit()
            for t in created:
                session.refresh(t)
            return [_serialize(t) for t in created]

    def update_ai(
        self,
        ticket_id: str,
        ai_payload: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._SessionFactory() as session:
            ticket = session.get(Ticket, ticket_id)
            if ticket is None or (user_id is not None and ticket.user_id != user_id):
                return None
            ticket.ai = ai_payload
            from .db import utcnow
            ticket.analyzed_at = utcnow()
            session.commit()
            session.refresh(ticket)
            return _serialize(ticket)

    def update_status(
        self,
        ticket_id: str,
        status: str,
        user_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._SessionFactory() as session:
            ticket = session.get(Ticket, ticket_id)
            if ticket is None or (user_id is not None and ticket.user_id != user_id):
                return None
            ticket.status = status
            session.commit()
            session.refresh(ticket)
            return _serialize(ticket)

    def delete(self, ticket_id: str, user_id: str | None = None) -> bool:
        with self._SessionFactory() as session:
            ticket = session.get(Ticket, ticket_id)
            if ticket is None or (user_id is not None and ticket.user_id != user_id):
                return False
            session.delete(ticket)
            session.commit()
            return True

    def clear(self, user_id: str | None = None) -> None:
        with self._SessionFactory() as session:
            stmt = select(Ticket)
            if user_id is not None:
                stmt = stmt.where(Ticket.user_id == user_id)
            for t in session.execute(stmt).scalars().all():
                session.delete(t)
            session.commit()


# ---------------------------------------------------------------------------
# CSV (unchanged from the JSON era)
# ---------------------------------------------------------------------------

def parse_csv(file_bytes: bytes) -> list[dict[str, str]]:
    """Parse an uploaded CSV. Expects headers; tolerates common synonyms."""
    text = file_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for raw in reader:
        norm = { (k or "").strip().lower(): (v or "").strip() for k, v in raw.items() if k }
        if not any(norm.values()):
            continue
        rows.append({
            "subject": norm.get("subject") or norm.get("title") or norm.get("summary", ""),
            "body": norm.get("body") or norm.get("description") or norm.get("message", ""),
            "requester": norm.get("requester") or norm.get("email") or norm.get("from", ""),
        })
    return rows
