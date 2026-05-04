"""Email sender with multiple backends.

Three modes, picked automatically based on env vars:

1. **smtp**     — set SMTP_HOST / SMTP_USER / SMTP_PASSWORD (e.g. Gmail).
2. **resend**   — set RESEND_API_KEY (https://resend.com, free 100/day).
3. **console**  — fallback when nothing is configured. Logs the email
                  body to stdout. Perfect for local dev and lets the
                  forgot-password flow keep working without setup.

The public surface is a single function: ``send_email(to, subject, body)``.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

import urllib.request
import urllib.error
import json

logger = logging.getLogger(__name__)


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASSWORD"))


def _resend_configured() -> bool:
    return bool(os.getenv("RESEND_API_KEY"))


def get_active_backend() -> str:
    if _smtp_configured():
        return "smtp"
    if _resend_configured():
        return "resend"
    return "console"


def _from_address() -> str:
    return (
        os.getenv("EMAIL_FROM")
        or os.getenv("SMTP_USER")
        or "no-reply@triagent.local"
    )


def _send_smtp(to: str, subject: str, body: str) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = _from_address()
    msg["To"] = to
    msg.set_content(body)

    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context, timeout=15) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls(context=context)
            smtp.login(user, password)
            smtp.send_message(msg)


def _send_resend(to: str, subject: str, body: str) -> None:
    api_key = os.environ["RESEND_API_KEY"]
    payload = json.dumps({
        "from": _from_address(),
        "to": [to],
        "subject": subject,
        "text": body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status >= 300:
                raise RuntimeError(f"resend returned {resp.status}: {resp.read()!r}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"resend HTTP {e.code}: {body}")


def _send_console(to: str, subject: str, body: str) -> None:
    print(
        "\n"
        "================ EMAIL (console backend) ================\n"
        f"To:      {to}\n"
        f"From:    {_from_address()}\n"
        f"Subject: {subject}\n"
        "---------------------------------------------------------\n"
        f"{body}\n"
        "=========================================================\n",
        flush=True,
    )


def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via the active backend. Returns the backend name used."""
    backend = get_active_backend()
    try:
        if backend == "smtp":
            _send_smtp(to, subject, body)
        elif backend == "resend":
            _send_resend(to, subject, body)
        else:
            _send_console(to, subject, body)
        logger.info("email sent via %s to %s", backend, to)
        return backend
    except Exception as exc:  # noqa: BLE001
        logger.error("email send via %s failed: %s — falling back to console", backend, exc)
        _send_console(to, subject, body)
        return "console"


# ---------------------------------------------------------------------------
# Templated emails
# ---------------------------------------------------------------------------

def send_password_reset_code(to: str, name: Optional[str], code: str) -> str:
    name = (name or to.split("@")[0]).strip()
    subject = "Triagent password reset code"
    body = (
        f"Hi {name},\n\n"
        f"Your Triagent password reset code is:\n\n"
        f"    {code}\n\n"
        f"Enter this code on the password reset screen to choose a new password. "
        f"It expires in 15 minutes and can only be used once.\n\n"
        f"If you didn't request this, you can safely ignore this email — "
        f"your password won't change.\n\n"
        f"— Triagent"
    )
    return send_email(to, subject, body)
