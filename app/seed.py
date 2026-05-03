"""Optional demo data so a fresh deploy is immediately usable.

Only runs when ``SEED_DEMO_DATA=1`` and the store is empty.
"""

from __future__ import annotations

from .storage import TicketStore

DEMO_TICKETS = [
    {
        "subject": "VPN keeps disconnecting every few minutes",
        "body": (
            "Cisco AnyConnect drops every 5-10 minutes since this morning. "
            "Internet itself works fine. I need this for production access — urgent, "
            "blocking my whole day."
        ),
        "requester": "alex.morgan@acme.com",
    },
    {
        "subject": "Locked out of Okta — password reset email never arrived",
        "body": (
            "I'm getting 'account locked' when trying to sign in to Okta SSO. "
            "Tried the self-service reset twice, no email in inbox or spam."
        ),
        "requester": "priya.shah@acme.com",
    },
    {
        "subject": "Dell XPS 13 won't turn on",
        "body": (
            "Pressed power button — no lights, no fan, totally dead. "
            "Tried two different chargers, no luck. Was working fine yesterday."
        ),
        "requester": "jordan.lee@acme.com",
    },
    {
        "subject": "Outlook stuck on 'Trying to connect'",
        "body": (
            "Outlook 365 has been showing 'Trying to connect…' for the last hour. "
            "Webmail works fine. Already restarted the laptop and re-opened Outlook."
        ),
        "requester": "sam.kim@acme.com",
    },
    {
        "subject": "Need access to the finance shared drive",
        "body": (
            "Hi — I just moved over to the FP&A team last week. Could I get read/write "
            "access to \\\\fileshare\\finance? My manager Lisa Chen approved the move."
        ),
        "requester": "dani.rivera@acme.com",
    },
    {
        "subject": "Slack desktop app crashes on launch (Windows 11)",
        "body": (
            "Slack desktop client crashes immediately when I open it. The browser "
            "version works fine. I've reinstalled twice, same crash on launch."
        ),
        "requester": "chris.wong@acme.com",
    },
    {
        "subject": "Wi-Fi outage on floor 3 — entire engineering team blocked",
        "body": (
            "All users on floor 3 lost Wi-Fi about 10 minutes ago. Wired connections "
            "still work. This is blocking the whole engineering org. P1."
        ),
        "requester": "noc@acme.com",
    },
    {
        "subject": "Question about Tableau install",
        "body": (
            "No rush at all — I'd just like Tableau Desktop installed when you have "
            "a spare moment. Whenever this week is fine."
        ),
        "requester": "morgan.taylor@acme.com",
    },
]


def maybe_seed(store: TicketStore) -> int:
    """Seed demo tickets if the store is empty. Returns count inserted."""
    if store.list():
        return 0
    created = store.bulk_add(DEMO_TICKETS)
    return len(created)
