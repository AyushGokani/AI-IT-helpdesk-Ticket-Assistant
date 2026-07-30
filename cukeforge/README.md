# CukeForge — Jira → Cucumber → green

> Standalone AI pipeline (lives in `/cukeforge` — **does not replace Triagent**).
> Pull a Jira story → generate Cucumber/Behave features + steps → run → auto-fix
> until the suite goes green.

## What it does

1. **Ingest** a Jira ticket (or built-in demo stories when Jira isn’t configured)
2. **Generate** a Gherkin `.feature` from summary + acceptance criteria
3. **Generate** Python Behave step definitions (in-memory domain model)
4. **Run** `behave` and capture pass/fail output
5. **Repair** failing steps with AI (or offline heuristic) and re-run until green

AI runs **only** on **Forge & pass tests** when `OPENAI_API_KEY` is set. Without a
key, the heuristic still greens the demo tickets on **$0**.

## Stack

- Python 3.12 · Flask 3 · Behave · OpenAI SDK (optional) · Jira REST (optional)
- Frontend: HTML + CSS + vanilla JS (no build step)

## Quick start

```bash
cd cukeforge
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python wsgi.py
```

Open http://127.0.0.1:5001 — pick a demo ticket → **Forge & pass tests**.

### Optional credentials (`.env`)

```
OPENAI_API_KEY=sk-...
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
```

## API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/health` | Service + Jira/AI mode |
| GET | `/api/tickets` | List Jira or demo tickets |
| GET | `/api/tickets/<key>` | Ticket detail |
| POST | `/api/runs` | `{ "ticket_key": "DEMO-101", "use_ai": true }` |
| GET | `/api/runs` | Recent runs |
| GET | `/api/runs/<id>` | Run detail |

## Tests

```bash
cd cukeforge
pytest -q
```

## Note on Triagent

Triagent remains the root app in this repository (`app/`, `frontend/`, etc.).
CukeForge is a **separate project** under `cukeforge/` with its own deps, UI,
and entrypoint.
