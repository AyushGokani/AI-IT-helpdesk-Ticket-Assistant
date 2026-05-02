"""Lightweight JSON-backed ticket store.

Avoids a database dependency so the app runs anywhere with zero setup.
Thread-safe enough for a demo via a per-instance lock.
"""

from __future__ import annotations

import csv
import io
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TicketStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _write(self, tickets: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(tickets, indent=2), encoding="utf-8")

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return sorted(
                self._read(),
                key=lambda t: t.get("created_at", ""),
                reverse=True,
            )

    def get(self, ticket_id: str) -> dict[str, Any] | None:
        with self._lock:
            for ticket in self._read():
                if ticket["id"] == ticket_id:
                    return ticket
        return None

    def add(
        self,
        subject: str,
        body: str,
        requester: str | None = None,
    ) -> dict[str, Any]:
        ticket = {
            "id": uuid.uuid4().hex[:10],
            "subject": (subject or "").strip() or "(no subject)",
            "body": (body or "").strip(),
            "requester": (requester or "").strip() or "unknown@example.com",
            "status": "open",
            "created_at": _now_iso(),
            "ai": None,
        }
        with self._lock:
            tickets = self._read()
            tickets.append(ticket)
            self._write(tickets)
        return ticket

    def bulk_add(self, rows: Iterable[dict[str, str]]) -> list[dict[str, Any]]:
        created: list[dict[str, Any]] = []
        with self._lock:
            tickets = self._read()
            for row in rows:
                ticket = {
                    "id": uuid.uuid4().hex[:10],
                    "subject": (row.get("subject") or "").strip() or "(no subject)",
                    "body": (row.get("body") or row.get("description") or "").strip(),
                    "requester": (row.get("requester") or row.get("email") or "unknown@example.com").strip(),
                    "status": "open",
                    "created_at": _now_iso(),
                    "ai": None,
                }
                tickets.append(ticket)
                created.append(ticket)
            self._write(tickets)
        return created

    def update_ai(self, ticket_id: str, ai_payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            tickets = self._read()
            for ticket in tickets:
                if ticket["id"] == ticket_id:
                    ticket["ai"] = ai_payload
                    ticket["analyzed_at"] = _now_iso()
                    self._write(tickets)
                    return ticket
        return None

    def update_status(self, ticket_id: str, status: str) -> dict[str, Any] | None:
        with self._lock:
            tickets = self._read()
            for ticket in tickets:
                if ticket["id"] == ticket_id:
                    ticket["status"] = status
                    self._write(tickets)
                    return ticket
        return None

    def delete(self, ticket_id: str) -> bool:
        with self._lock:
            tickets = self._read()
            new_tickets = [t for t in tickets if t["id"] != ticket_id]
            if len(new_tickets) == len(tickets):
                return False
            self._write(new_tickets)
            return True

    def clear(self) -> None:
        with self._lock:
            self._write([])

    def stats(self) -> dict[str, Any]:
        tickets = self.list()
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
