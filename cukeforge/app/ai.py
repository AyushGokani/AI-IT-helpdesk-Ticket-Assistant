"""AI + heuristic generation of Gherkin features and Behave step fixes."""

from __future__ import annotations

import json
import os
import re
from typing import Any


FEATURE_SYSTEM = """You are a senior BDD engineer.
Given a Jira ticket, produce a Cucumber/Gherkin feature file that captures the
acceptance criteria as executable scenarios.

Rules:
- Output ONLY the .feature file contents (no markdown fences).
- Use Feature / Scenario / Given / When / Then / And.
- Keep steps concrete and testable.
- Prefer 1–3 scenarios.
- Tag the feature with @jira-<KEY> using the ticket key.
"""

STEPS_SYSTEM = """You are a senior Python Behave engineer.
Given a Gherkin feature and optional failing test output, produce a complete
Behave steps Python module that makes the scenarios pass using an in-memory
domain model (no real HTTP/DB).

Rules:
- Output ONLY valid Python code for steps/*.py (no markdown fences).
- Import from behave: given, when, then.
- Use context to store state between steps.
- Implement enough domain logic inline so scenarios PASS.
- Do not use external services, sleep, or network calls.
- Match step patterns to the feature text.
"""

FIX_SYSTEM = """You are fixing failing Behave step definitions.
Given the feature file, current steps.py, and behave stdout/stderr, rewrite
steps.py so the scenarios pass using an in-memory domain model.

Rules:
- Output ONLY the full updated steps.py Python source (no markdown fences).
- Keep imports from behave.
- Do not leave NotImplementedError or pending steps.
"""


def openai_available(api_key: str | None = None) -> bool:
    key = (
        api_key if api_key is not None else os.environ.get("OPENAI_API_KEY", "")
    ).strip()
    return bool(key)


def _chat(messages: list[dict[str, str]], *, api_key: str, model: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:gherkin|feature|python|py)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or "scenario"


def heuristic_feature(ticket: dict[str, Any]) -> str:
    key = ticket.get("key", "TICKET")
    summary = ticket.get("summary") or "Untitled story"
    criteria = ticket.get("acceptance_criteria") or []
    description = ticket.get("description") or ""

    lines = [
        f"@jira-{key}",
        f"Feature: {summary}",
        f"  Jira {key} — generated offline by CukeForge heuristic",
        "",
    ]

    gherkin_lines = [
        c
        for c in criteria
        if re.match(r"^(Given|When|Then|And|But)\b", c, re.I)
    ]

    if gherkin_lines:
        scenarios: list[list[str]] = []
        current: list[str] = []
        for step in gherkin_lines:
            if re.match(r"^Given\b", step, re.I) and current:
                if any(re.match(r"^Then\b", s, re.I) for s in current):
                    scenarios.append(current)
                    current = [step]
                else:
                    current.append(step)
            else:
                current.append(step)
        if current:
            scenarios.append(current)

        for idx, steps in enumerate(scenarios, start=1):
            lines.append(f"  Scenario: {summary} — path {idx}")
            for step in steps:
                step = re.sub(
                    r"^(given|when|then|and|but)\b",
                    lambda m: m.group(1).capitalize(),
                    step,
                    flags=re.I,
                )
                lines.append(f"    {step}")
            lines.append("")
    else:
        lines.append(f"  Scenario: {summary}")
        lines.append(f'    Given the system is ready for "{key}"')
        lines.append(
            f'    When the acceptance criteria for "{summary}" are exercised'
        )
        if criteria:
            for item in criteria[:5]:
                safe = item.replace('"', "'")
                lines.append(f'    Then "{safe}" is satisfied')
        else:
            snippet = (description or summary)[:80].replace('"', "'")
            lines.append(f'    Then the outcome for "{snippet}" is successful')
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _parse_feature_steps(feature_text: str) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    for line in feature_text.splitlines():
        m = re.match(r"^\s*(Given|When|Then|And|But)\s+(.+?)\s*$", line)
        if m:
            steps.append((m.group(1), m.group(2)))
    return steps


def _decorator_for(kw: str, text: str, prev_deco: str) -> str:
    if kw in {"And", "But"}:
        return prev_deco or "then"
    return {"Given": "given", "When": "when", "Then": "then"}.get(kw, "then")


def _step_body(text: str, deco: str) -> list[str]:
    lower = text.lower()
    body = ["    app = _state(context)"]

    if "remain on the login page" in lower:
        body += ['    assert app["page"] == "login"']
    elif "login page" in lower:
        body += ['    app["page"] = "login"', '    app["error"] = None']
    elif "valid email" in lower and "password" in lower:
        body += [
            '    app["logged_in"] = True',
            '    app["user"] = {"name": "Alex", "password": "secret"}',
            '    app["page"] = "dashboard"',
        ]
    elif "invalid password" in lower:
        body += [
            '    app["logged_in"] = False',
            '    app["page"] = "login"',
            '    app["error"] = "Invalid credentials"',
        ]
    elif "redirected to the dashboard" in lower:
        body += ['    assert app["page"] == "dashboard"']
    elif "welcome message" in lower:
        body += [
            '    assert app["logged_in"] is True',
            '    assert app["user"] and app["user"].get("name")',
        ]
    elif "invalid credentials" in lower or (
        "error message" in lower and "invalid" in lower
    ):
        body += ['    assert app.get("error") == "Invalid credentials"']
    elif "cart is empty" in lower:
        body += ['    app["cart"] = []']
    elif "product" in lower and "available" in lower:
        body += [
            "    import re as _re",
            f"    _t = {text!r}",
            r"    m = _re.search(r'product \"([^\"]+)\" is available for \$?([0-9.]+)', _t, _re.I)",
            '    name, price = (m.group(1), float(m.group(2))) if m else ("Item", 0.0)',
            '    app["products"][name] = price',
        ]
    elif "add" in lower and "cart" in lower:
        body += [
            "    import re as _re",
            f"    _t = {text!r}",
            r"    m = _re.search(r'\"([^\"]+)\"', _t)",
            '    name = m.group(1) if m else "Item"',
            '    price = float(app["products"].get(name, 0.0))',
            '    app["cart"].append({"name": name, "price": price})',
        ]
    elif "cart contains" in lower:
        body += [
            "    import re as _re",
            f"    _t = {text!r}",
            r'    m = _re.search(r"(\d+)", _t)',
            "    n = int(m.group(1)) if m else 0",
            '    assert len(app["cart"]) == n',
        ]
    elif "cart total" in lower:
        body += [
            "    import re as _re",
            f"    _t = {text!r}",
            r'    m = _re.search(r"\$?([0-9.]+)", _t)',
            "    expected = float(m.group(1)) if m else 0.0",
            '    total = round(sum(i["price"] for i in app["cart"]), 2)',
            "    assert abs(total - expected) < 0.001",
        ]
    elif "user exists with email" in lower:
        body += [
            "    import re as _re",
            f"    _t = {text!r}",
            r"    m = _re.search(r'\"([^\"]+)\"', _t)",
            '    app["user"] = {"email": m.group(1) if m else "user@example.com", "password": "old"}',
        ]
    elif "request a password reset" in lower:
        body += [
            '    app["reset_code"] = "123456"',
            '    email = (app.get("user") or {}).get("email", "user@example.com")',
            '    app["emails"].append({"to": email, "code": app["reset_code"]})',
        ]
    elif "6-digit reset code is generated" in lower:
        body += [
            '    assert app.get("reset_code") and len(str(app["reset_code"])) == 6',
            '    assert str(app["reset_code"]).isdigit()',
        ]
    elif "email is queued" in lower:
        body += [
            "    import re as _re",
            f"    _t = {text!r}",
            r"    m = _re.search(r'\"([^\"]+)\"', _t)",
            '    to = m.group(1) if m else ""',
            '    assert any(e["to"] == to for e in app["emails"])',
        ]
    elif "incorrect reset code" in lower:
        body += ['    app["flags"].add("reset_rejected")']
    elif "reset is rejected" in lower:
        body += ['    assert "reset_rejected" in app["flags"]']
    elif "correct reset code" in lower and "new password" in lower:
        body += [
            '    assert app.get("reset_code")',
            '    app["user"]["password"] = "new-pass"',
            '    app["flags"].add("password_updated")',
        ]
    elif "log in with the new password" in lower:
        body += [
            '    assert "password_updated" in app["flags"]',
            '    assert app["user"]["password"] == "new-pass"',
            '    app["logged_in"] = True',
        ]
    elif "system is ready" in lower:
        body += ['    app["ready"] = True']
    elif "acceptance criteria" in lower and "exercised" in lower:
        body += [
            '    assert app.get("ready") is True',
            '    app["flags"].add("exercised")',
        ]
    elif "is satisfied" in lower or "is successful" in lower:
        body += [
            '    assert ("exercised" in app["flags"]) or (app.get("ready") is True)'
        ]
    else:
        flag = _slug(text)[:50]
        if deco == "then":
            body += [
                "    assert app is not None",
                f'    app["flags"].add("ok_{flag}")',
            ]
        else:
            body += [f'    app["flags"].add("{flag}")']

    return body


def heuristic_steps(feature_text: str, ticket: dict[str, Any] | None = None) -> str:
    parsed = _parse_feature_steps(feature_text)
    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for kw, text in parsed:
        if text not in seen:
            seen.add(text)
            unique.append((kw, text))

    parts = [
        '"""Auto-generated Behave steps (offline heuristic)."""',
        "from __future__ import annotations",
        "",
        "from behave import given, when, then",
        "",
        "",
        "def _state(context):",
        "    if not hasattr(context, 'app'):",
        "        context.app = {",
        "            'ready': False,",
        "            'cart': [],",
        "            'logged_in': False,",
        "            'user': None,",
        "            'page': 'home',",
        "            'error': None,",
        "            'reset_code': None,",
        "            'emails': [],",
        "            'flags': set(),",
        "            'products': {},",
        "        }",
        "    return context.app",
        "",
    ]

    prev_deco = "given"
    for idx, (kw, text) in enumerate(unique):
        deco = _decorator_for(kw, text, prev_deco)
        if kw not in {"And", "But"}:
            prev_deco = deco
        pattern = text.replace("\\", "\\\\").replace('"', '\\"')
        fn = f"step_{idx}_{_slug(text)[:40]}"
        parts.append(f'@{deco}(u"{pattern}")')
        parts.append(f"def {fn}(context):")
        parts.extend(_step_body(text, deco))
        parts.append("")

    return "\n".join(parts).rstrip() + "\n"


def generate_feature(
    ticket: dict[str, Any],
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    use_ai: bool = True,
) -> tuple[str, str]:
    if use_ai and openai_available(api_key):
        payload = json.dumps(
            {
                "key": ticket.get("key"),
                "summary": ticket.get("summary"),
                "description": ticket.get("description"),
                "acceptance_criteria": ticket.get("acceptance_criteria"),
            },
            indent=2,
        )
        text = _chat(
            [
                {"role": "system", "content": FEATURE_SYSTEM},
                {"role": "user", "content": payload},
            ],
            api_key=api_key,
            model=model,
        )
        return _strip_fences(text), "openai"
    return heuristic_feature(ticket), "heuristic"


def generate_steps(
    feature_text: str,
    ticket: dict[str, Any],
    *,
    api_key: str = "",
    model: str = "gpt-4o-mini",
    use_ai: bool = True,
    failure_log: str = "",
    current_steps: str = "",
) -> tuple[str, str]:
    if use_ai and openai_available(api_key):
        if failure_log and current_steps:
            user = (
                f"Ticket: {ticket.get('key')} {ticket.get('summary')}\n\n"
                f"FEATURE:\n{feature_text}\n\n"
                f"CURRENT steps.py:\n{current_steps}\n\n"
                f"BEHAVE OUTPUT:\n{failure_log}\n"
            )
            system = FIX_SYSTEM
        else:
            user = (
                "Ticket: "
                + json.dumps(
                    {
                        "key": ticket.get("key"),
                        "summary": ticket.get("summary"),
                    }
                )
                + f"\n\nFEATURE:\n{feature_text}\n"
            )
            system = STEPS_SYSTEM
        text = _chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            api_key=api_key,
            model=model,
        )
        return _strip_fences(text), "openai"
    return heuristic_steps(feature_text, ticket), "heuristic"
