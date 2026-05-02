# AI Helpdesk Ticket Assistant

Triage IT support tickets with AI — **only when you click Generate**. Built to be
demo-ready on zero credits (heuristic fallback) and production-ready when you
plug in an OpenAI key.

For each ticket the assistant will:

1. **Classify** the issue (network · login · hardware · software · email · access · billing · other)
2. **Score priority** (low / medium / high / urgent)
3. **Suggest concrete resolution steps**
4. **Draft a polite, ready-to-send reply** to the requester

> Resume line: *Built an AI-powered ticket triage system that classifies, prioritizes,
> and drafts replies on demand — cutting manual triage time on a 500-ticket sample
> from minutes to seconds per ticket.*

---

## Why this is cheap to run

- AI is **only invoked when the user clicks "Generate AI triage"** on a specific
  ticket. No background calls, no per-keystroke calls, no auto-classification on
  upload.
- A keyword **heuristic fallback** runs instantly and locally when no
  `OPENAI_API_KEY` is set, so the whole demo works on **0 credits**.
- Heuristic is also exposed as a per-call **"offline" toggle** in the UI, so you
  can still triage without spending tokens once a key is configured.

---

## Stack

- **Backend:** Python 3.10+ · Flask 3 · OpenAI SDK
- **Storage:** JSON file (zero-config; swap for Postgres later if you want)
- **Frontend:** single-page HTML + Tailwind (CDN) + vanilla JS — no build step
- **Tests:** pytest

```
.
├── app/
│   ├── __init__.py     # Flask factory
│   ├── routes.py       # /api/* endpoints
│   ├── ai.py           # OpenAI call + heuristic fallback
│   └── storage.py      # JSON ticket store + CSV parser
├── frontend/
│   ├── index.html      # UI shell (Tailwind)
│   ├── app.js          # SPA logic, AI calls only on Generate click
│   ├── styles.css
│   └── sample_tickets.csv
├── tests/              # pytest suite
├── wsgi.py             # entrypoint
├── requirements.txt
└── .env.example
```

---

## Quick start

```bash
git clone <this-repo> ai-helpdesk
cd ai-helpdesk
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # optional — works without a key
python wsgi.py                # → http://127.0.0.1:5000
```

Open the app, click **+ New ticket** (or upload `frontend/sample_tickets.csv`),
select a ticket, and hit **Generate AI triage**.

### Enabling real AI

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini   # cheapest model that's good enough; change as needed
```

Restart the server. The badge in the top-right will switch from
*heuristic mode* to `AI: gpt-4o-mini`. You'll get an extra "Use offline
heuristic (no API call)" checkbox to bypass the LLM for any individual ticket.

---

## How AI calls are gated

```py
# app/routes.py
@bp.post("/tickets/<ticket_id>/analyze")
def analyze_ticket(ticket_id):
    """On-demand AI analysis. Triggered ONLY by the user's Generate click."""
    ...
```

```js
// frontend/app.js
document.getElementById("generate-btn").addEventListener("click", onGenerate);
```

There is **no** code path anywhere else that hits OpenAI. List, create,
upload, status, and delete endpoints never touch the API.

---

## API

| Method | Path                              | What it does                                   |
| ------ | --------------------------------- | ---------------------------------------------- |
| GET    | `/api/health`                     | Health + whether an API key is configured      |
| GET    | `/api/tickets`                    | List tickets (newest first)                    |
| POST   | `/api/tickets`                    | Create a ticket `{subject, body, requester}`   |
| GET    | `/api/tickets/<id>`               | Get one ticket                                 |
| POST   | `/api/tickets/<id>/analyze`       | **Run AI triage** (`{"offline": true}` to force heuristic) |
| POST   | `/api/tickets/<id>/status`        | Update status `{open, in_progress, resolved}`  |
| DELETE | `/api/tickets/<id>`               | Delete                                         |
| POST   | `/api/tickets/upload`             | Bulk upload CSV (multipart `file`)             |
| POST   | `/api/tickets/clear`              | Wipe all tickets                               |
| GET    | `/api/stats`                      | Counts by status, category, priority           |

CSV columns (case-insensitive, common synonyms accepted):
`subject` · `body` (or `description`) · `requester` (or `email`).

---

## Tests

```bash
pytest -q
```

15 tests cover the heuristic classifier, the OpenAI fallback path
(monkey-patched), and every JSON endpoint. The whole suite runs in
under a second.

---

## Roadmap ideas

- Swap the JSON store for Postgres + SQLAlchemy
- Add a Zendesk webhook that POSTs incoming tickets into `/api/tickets`
- Background job to **batch-triage** on schedule (still gated behind a button on the UI)
- Authentication + per-user views
- Per-category accuracy dashboard once you have a labeled set
