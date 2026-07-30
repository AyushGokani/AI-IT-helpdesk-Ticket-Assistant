"""Jira ticket fetch with offline demo fallback."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests


def jira_configured(base_url: str, email: str, token: str) -> bool:
    return bool(base_url and email and token and "your-domain" not in base_url)


def load_demo_tickets(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "\n".join(_adf_to_text(n) for n in node)
    if isinstance(node, dict):
        text = node.get("text", "")
        children = "".join(_adf_to_text(c) for c in node.get("content", []))
        ntype = node.get("type", "")
        if ntype in {"paragraph", "heading", "listItem", "blockquote"}:
            return (text + children).rstrip() + "\n"
        if ntype == "hardBreak":
            return "\n"
        return text + children
    return str(node)


def _extract_acceptance_criteria(description: str, fields: dict[str, Any]) -> list[str]:
    criteria: list[str] = []
    for key, value in fields.items():
        if not key:
            continue
        lkey = key.lower()
        if "acceptance" in lkey or lkey.endswith("ac"):
            if isinstance(value, str) and value.strip():
                criteria.extend(
                    line.strip(" -*\t")
                    for line in value.splitlines()
                    if line.strip()
                )
            elif isinstance(value, dict):
                text = _adf_to_text(value)
                criteria.extend(
                    line.strip(" -*\t")
                    for line in text.splitlines()
                    if line.strip()
                )

    if criteria:
        return [c for c in criteria if c]

    if description:
        for line in description.splitlines():
            cleaned = line.strip(" -*\t")
            if re.match(r"^(Given|When|Then|And|But)\b", cleaned, flags=re.IGNORECASE):
                criteria.append(cleaned)
            elif re.match(r"^\d+[.)]\s+", cleaned):
                criteria.append(re.sub(r"^\d+[.)]\s+", "", cleaned))
    return criteria


def normalize_issue(raw: dict[str, Any]) -> dict[str, Any]:
    fields = raw.get("fields") or {}
    description = fields.get("description")
    if isinstance(description, dict):
        description = _adf_to_text(description).strip()
    elif description is None:
        description = ""
    else:
        description = str(description).strip()

    status = (fields.get("status") or {}).get("name", "Unknown")
    issue_type = (fields.get("issuetype") or {}).get("name", "Story")
    priority = (fields.get("priority") or {}).get("name", "Medium")
    labels = fields.get("labels") or []

    return {
        "key": raw.get("key", "UNKNOWN"),
        "summary": fields.get("summary") or "",
        "issue_type": issue_type,
        "status": status,
        "priority": priority,
        "description": description,
        "acceptance_criteria": _extract_acceptance_criteria(description, fields),
        "labels": labels,
        "source": "jira",
    }


def fetch_jira_tickets(
    base_url: str,
    email: str,
    token: str,
    jql: str,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    url = f"{base_url}/rest/api/3/search"
    resp = requests.get(
        url,
        params={
            "jql": jql,
            "maxResults": max_results,
            "fields": "summary,description,status,issuetype,priority,labels",
        },
        auth=(email, token),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    issues = resp.json().get("issues") or []
    return [normalize_issue(issue) for issue in issues]


def fetch_jira_ticket(
    base_url: str,
    email: str,
    token: str,
    key: str,
) -> dict[str, Any]:
    url = f"{base_url}/rest/api/3/issue/{key}"
    resp = requests.get(
        url,
        params={"fields": "summary,description,status,issuetype,priority,labels"},
        auth=(email, token),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    return normalize_issue(resp.json())


def list_tickets(
    *,
    demo_path: Path,
    base_url: str = "",
    email: str = "",
    token: str = "",
    jql: str = "",
) -> tuple[list[dict[str, Any]], str]:
    if jira_configured(base_url, email, token):
        tickets = fetch_jira_tickets(
            base_url, email, token, jql or "order by updated DESC"
        )
        for t in tickets:
            t["source"] = "jira"
        return tickets, "jira"

    tickets = load_demo_tickets(demo_path)
    for t in tickets:
        t["source"] = "demo"
    return tickets, "demo"


def get_ticket(
    key: str,
    *,
    demo_path: Path,
    base_url: str = "",
    email: str = "",
    token: str = "",
) -> dict[str, Any]:
    if jira_configured(base_url, email, token):
        ticket = fetch_jira_ticket(base_url, email, token, key)
        ticket["source"] = "jira"
        return ticket

    for ticket in load_demo_tickets(demo_path):
        if ticket["key"].upper() == key.upper():
            ticket = dict(ticket)
            ticket["source"] = "demo"
            return ticket
    raise KeyError(f"Ticket {key} not found in demo set")
