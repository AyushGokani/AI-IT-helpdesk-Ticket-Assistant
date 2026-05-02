"""On-demand ticket analysis.

Two modes:
1. ``llm_classify`` — calls OpenAI (only when the user clicks Generate AND a key is
   configured). Returns category, priority, suggested resolution steps, and a
   ready-to-send reply draft.
2. ``heuristic_classify`` — keyword-based fallback so the app is fully usable
   for demos / offline / zero-credit scenarios.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


CATEGORIES = [
    "network",
    "login",
    "hardware",
    "software",
    "email",
    "access",
    "billing",
    "other",
]

PRIORITIES = ["low", "medium", "high", "urgent"]


# ---------------------------------------------------------------------------
# Heuristic fallback
# ---------------------------------------------------------------------------

_KEYWORDS: dict[str, list[str]] = {
    "network": [
        "vpn", "wifi", "wi-fi", "internet", "ethernet", "router", "dns",
        "ping", "connection", "offline", "disconnect", "slow network",
        "no network", "proxy", "firewall",
    ],
    "login": [
        "password", "login", "log in", "sign in", "signin", "mfa", "2fa",
        "otp", "locked out", "account locked", "sso", "okta", "reset",
        "credential",
    ],
    "hardware": [
        "laptop", "monitor", "keyboard", "mouse", "battery", "charger",
        "screen", "printer", "headset", "webcam", "dock", "usb", "broken",
        "cracked", "won't turn on", "won t turn on", "wont turn on",
        "blue screen", "bsod",
    ],
    "software": [
        "install", "uninstall", "update", "crash", "error", "freeze",
        "frozen", "bug", "outlook", "excel", "word", "teams", "slack",
        "zoom", "chrome", "edge", "license",
    ],
    "email": [
        "email", "mailbox", "outlook", "gmail", "smtp", "imap",
        "spam", "phishing", "calendar invite", "shared mailbox",
    ],
    "access": [
        "access", "permission", "share folder", "shared drive", "file share",
        "github access", "repo access", "group", "ad group", "role",
    ],
    "billing": [
        "invoice", "billing", "charge", "subscription", "renewal", "refund",
        "payment", "license cost",
    ],
}

_URGENT_HINTS = [
    "outage", "down", "production down", "p1", "all users",
    "company-wide", "company wide", "cannot work", "can't work",
    "blocking", "urgent", "asap", "critical",
]
_HIGH_HINTS = ["important", "soon", "today", "deadline", "demo"]
_LOW_HINTS = ["whenever", "no rush", "low priority", "fyi", "question"]


def _score_category(text: str) -> tuple[str, dict[str, int]]:
    text_l = text.lower()
    scores: dict[str, int] = {c: 0 for c in CATEGORIES}
    for cat, words in _KEYWORDS.items():
        for w in words:
            if w in text_l:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other", scores
    return best, scores


def _score_priority(text: str) -> str:
    text_l = text.lower()
    if any(h in text_l for h in _URGENT_HINTS):
        return "urgent"
    if any(h in text_l for h in _HIGH_HINTS):
        return "high"
    if any(h in text_l for h in _LOW_HINTS):
        return "low"
    return "medium"


_RESOLUTIONS: dict[str, list[str]] = {
    "network": [
        "Confirm scope: single user vs. site-wide outage.",
        "Have user run `ping 8.8.8.8` and `nslookup company.com`.",
        "Toggle Wi-Fi / re-connect VPN; reboot router/switch if on-prem.",
        "Check status page for ISP / VPN provider incidents.",
    ],
    "login": [
        "Verify the username and target system (SSO vs. local).",
        "Trigger a self-service password reset or admin reset.",
        "Confirm MFA device is enrolled and in sync; re-issue OTP if needed.",
        "Unlock the account in the directory if locked by failed attempts.",
    ],
    "hardware": [
        "Capture make/model, serial, and a photo if there is physical damage.",
        "Run vendor diagnostics (e.g. Dell SupportAssist, HP PC Hardware Diagnostics).",
        "Try a known-good cable/peripheral to isolate the failure.",
        "If under warranty, open an RMA; otherwise quote a replacement.",
    ],
    "software": [
        "Get exact app name, version, and full error text or screenshot.",
        "Try restart → re-login → reinstall (in that order).",
        "Check known issues / vendor release notes for the version.",
        "If reproducible, escalate to the application owner with repro steps.",
    ],
    "email": [
        "Confirm whether the issue is send, receive, or both.",
        "Check mailbox quota and recently changed rules/forwards.",
        "Verify mail-flow in the admin console; review message trace.",
        "Re-create the Outlook profile if client-side corruption is suspected.",
    ],
    "access": [
        "Confirm the exact resource (path, repo, app) and required role.",
        "Validate the request against the access matrix / manager approval.",
        "Add user to the appropriate AD / IdP group; avoid direct ACLs.",
        "Ask user to sign out / sign back in to refresh tokens.",
    ],
    "billing": [
        "Pull the latest invoice and the relevant subscription record.",
        "Confirm billing contact and PO number on file.",
        "Loop in Finance for refunds or credit notes.",
    ],
    "other": [
        "Acknowledge receipt and ask 1–2 clarifying questions.",
        "Reproduce or gather evidence (screenshots, logs, timestamps).",
        "Route to the correct queue once category is confirmed.",
    ],
}


def _reply_draft(category: str, ticket: dict[str, Any]) -> str:
    name = (ticket.get("requester") or "").split("@")[0].split(".")[0].title() or "there"
    subject = ticket.get("subject", "your issue")
    steps = _RESOLUTIONS.get(category, _RESOLUTIONS["other"])
    bullet_steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(steps[:3]))
    return (
        f"Hi {name},\n\n"
        f"Thanks for reaching out about \"{subject}\". I'm picking this up now.\n\n"
        f"To get you back up and running, here's what I'll try first:\n"
        f"{bullet_steps}\n\n"
        f"Could you confirm when this started and whether anyone else on your team "
        f"is seeing the same thing? I'll keep this ticket updated as I work.\n\n"
        f"Best,\nIT Helpdesk"
    )


def heuristic_classify(ticket: dict[str, Any]) -> dict[str, Any]:
    text = f"{ticket.get('subject', '')}\n{ticket.get('body', '')}"
    category, scores = _score_category(text)
    priority = _score_priority(text)
    total_hits = sum(scores.values())
    confidence = min(0.95, 0.5 + 0.1 * total_hits) if total_hits else 0.4
    return {
        "category": category,
        "priority": priority,
        "confidence": round(confidence, 2),
        "summary": _summarize(text),
        "resolution_steps": _RESOLUTIONS.get(category, _RESOLUTIONS["other"]),
        "reply_draft": _reply_draft(category, ticket),
        "source": "heuristic",
    }


def _summarize(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= 180:
        return cleaned
    return cleaned[:177].rsplit(" ", 1)[0] + "…"


# ---------------------------------------------------------------------------
# OpenAI path
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an experienced IT helpdesk lead. Triage one support ticket. "
    "Respond with STRICT JSON matching this schema and nothing else:\n"
    "{\n"
    '  "category": one of ' + json.dumps(CATEGORIES) + ",\n"
    '  "priority": one of ' + json.dumps(PRIORITIES) + ",\n"
    '  "confidence": number between 0 and 1,\n'
    '  "summary": one short sentence,\n'
    '  "resolution_steps": array of 3-5 short imperative steps,\n'
    '  "reply_draft": a polite, ready-to-send reply to the requester\n'
    "}"
)


def llm_classify(ticket: dict[str, Any], api_key: str, model: str) -> dict[str, Any]:
    """Call OpenAI for a single ticket. Raises on failure so the caller can fall back."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    user_payload = {
        "subject": ticket.get("subject", ""),
        "body": ticket.get("body", ""),
        "requester": ticket.get("requester", ""),
    }
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = response.choices[0].message.content or "{}"
    data = json.loads(raw)

    category = data.get("category", "other")
    if category not in CATEGORIES:
        category = "other"
    priority = data.get("priority", "medium")
    if priority not in PRIORITIES:
        priority = "medium"
    steps = data.get("resolution_steps") or []
    if not isinstance(steps, list):
        steps = [str(steps)]
    return {
        "category": category,
        "priority": priority,
        "confidence": float(data.get("confidence", 0.7)),
        "summary": str(data.get("summary", "")).strip() or _summarize(
            f"{ticket.get('subject','')} {ticket.get('body','')}"
        ),
        "resolution_steps": [str(s) for s in steps][:5],
        "reply_draft": str(data.get("reply_draft") or _reply_draft(category, ticket)),
        "source": f"openai:{model}",
    }


def analyze(ticket: dict[str, Any], api_key: str, model: str) -> dict[str, Any]:
    """Try LLM, fall back to heuristic on any error or missing key."""
    if api_key:
        try:
            return llm_classify(ticket, api_key=api_key, model=model)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OpenAI call failed, falling back to heuristic: %s", exc)
    return heuristic_classify(ticket)
