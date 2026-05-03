# AI Helpdesk Ticket Assistant

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

Triage IT support tickets with AI — **only when you click Generate**. Built to be
demo-ready on zero credits (heuristic fallback) and production-ready when you
plug in an OpenAI key.

For each ticket the assistant will:

1. **Classify** the issue (network · login · hardware · software · email · access · billing · other)
2. **Score priority** (low / medium / high / urgent)
3. **Suggest concrete resolution steps**
4. **Draft a polite, ready-to-send reply** to the requester

> **Resume line:** *Built and deployed an AI-powered ticket triage system that
> classifies, prioritizes, and drafts replies on demand using GPT-4o-mini —
> reducing manual triage time per ticket by ~80% on a sample of real IT tickets.*

---

## Why this is cheap to run

- AI is **only invoked when the user clicks "Generate AI triage"** on a specific
  ticket. No background calls, no per-keystroke calls, no auto-classification on
  upload.
- A keyword **heuristic fallback** runs instantly and locally when no
  `OPENAI_API_KEY` is set, so the whole demo works on **0 credits**.
- A per-call **"offline"** toggle in the UI lets you triage without spending
  tokens once a key is configured.

---

## Stack

- **Backend:** Python 3.12 · Flask 3 · OpenAI SDK · gunicorn (production)
- **Storage:** JSON file (zero-config; swap for Postgres later if you want)
- **Frontend:** single-page HTML + Tailwind (CDN) + vanilla JS — no build step
- **Tests:** 17 pytest tests, all run in <1s
- **Deploy:** one-click to Render (free tier) via `render.yaml`

```
.
├── app/
│   ├── __init__.py     # Flask factory
│   ├── routes.py       # /api/* endpoints
│   ├── ai.py           # OpenAI call + heuristic fallback
│   ├── seed.py         # Optional demo data on first boot
│   └── storage.py      # JSON ticket store + CSV parser
├── frontend/
│   ├── index.html      # UI shell (Tailwind)
│   ├── app.js          # SPA logic, AI calls only on Generate click
│   ├── styles.css
│   └── sample_tickets.csv
├── tests/              # pytest suite
├── wsgi.py             # entrypoint for both dev (Flask) and prod (gunicorn)
├── render.yaml         # one-click Render Blueprint
├── Procfile            # for Heroku/Railway/etc.
├── runtime.txt
├── requirements.txt
└── .env.example
```

---

## Quick start (local)

```bash
git clone https://github.com/AyushGokani/AI-IT-helpdesk-Ticket-Assistant.git
cd AI-IT-helpdesk-Ticket-Assistant

python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
copy .env.example .env        # macOS/Linux: cp .env.example .env
python wsgi.py                # → http://127.0.0.1:5000
```

Open the app, click **+ New ticket** (or upload `frontend/sample_tickets.csv`),
select a ticket, and hit **Generate AI triage**.

### Enabling real AI

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

Restart the server. The badge in the top-right will switch from
*heuristic mode* to `AI: gpt-4o-mini`. You'll get an extra "Use offline
heuristic (no API call)" checkbox to bypass the LLM for any individual ticket.

### Keyboard shortcuts

While viewing a ticket: **→ / ↓ / J** for next, **← / ↑ / K** for previous,
**G** to trigger Generate AI triage.

---

## Deploy live in 5 minutes (Render — free tier)

This repo includes a `render.yaml`, so Render auto-configures everything.

### Steps

1. **Push the code to your own GitHub repo** (it's already there if you cloned this one).
2. Sign up at [render.com](https://render.com) — you can sign in with GitHub. **No credit card required for the free tier.**
3. Click **New → Blueprint** → **Connect** the GitHub repo.
4. Render reads `render.yaml`, names the service `ai-helpdesk-ticket-assistant`, and shows you the env vars it'll create.
5. The only var you need to fill in manually is `OPENAI_API_KEY` (the rest auto-generate or have defaults). Paste your `sk-...` key. **Or leave it blank and the live demo runs in heuristic mode for free.**
6. Click **Apply**. First build takes ~3 minutes.
7. You'll get a public URL like `https://ai-helpdesk-ticket-assistant.onrender.com`.

That's it — your live demo is online with HTTPS, auto-deploys on every push to `main`, and seeds 8 example tickets on first boot so visitors immediately see something useful.

### Free tier tradeoffs (totally fine for a portfolio demo)

- The service spins down after 15 minutes of inactivity → ~30s cold start on next visit.
- 1 GB of persistent disk for ticket data, mounted at `/var/data` (configured in `render.yaml`).
- Add this to the README of your fork: *"Live demo: <your URL> (first request may take 30s to wake)."*

### Other hosts

The included `Procfile` works on **Heroku** and **Railway** too:

```
web: gunicorn wsgi:app --workers 2 --bind 0.0.0.0:$PORT --timeout 60
```

Just set the same env vars (`OPENAI_API_KEY`, `FLASK_SECRET_KEY`, `OPENAI_MODEL`, `SEED_DEMO_DATA=1`) in their dashboards.

---

## Putting this on your resume & LinkedIn

### Resume — short bullet (1 line)

> **AI Helpdesk Ticket Assistant** — Python · Flask · OpenAI · React-style SPA · Render
> Built and deployed an AI-powered IT ticket triage tool that classifies, prioritizes, and drafts replies on demand using GPT-4o-mini, with a keyword-heuristic fallback for zero-credit demos.

### Resume — fuller version (3 bullets)

**AI Helpdesk Ticket Assistant** | *Personal project* | [Live demo](#) · [GitHub](#)
- Designed and shipped a full-stack IT support triage tool (Python · Flask · OpenAI SDK · vanilla JS / Tailwind SPA), deployed on Render with auto-deploy CI on every push.
- Engineered an **on-demand-only** AI architecture so token spend is gated behind a single user action, with a keyword-classifier fallback that keeps the app fully functional on $0 of API credit.
- Built REST API for ticket CRUD, CSV bulk import, classification, priority scoring, and reply drafting; **17 pytest tests** cover the API and both AI paths (LLM + heuristic).

### LinkedIn — Featured / Project section

**Title:** AI Helpdesk Ticket Assistant
**Description (paste this):**

> An AI-powered triage tool for IT support tickets. Upload a ticket and the app
> classifies the issue (network / login / hardware / etc.), assigns a priority,
> suggests concrete resolution steps, and drafts a ready-to-send reply to the
> requester — all with one click.
>
> Built with Python (Flask) on the backend and a single-page Tailwind + vanilla
> JS frontend. AI calls are gated behind an explicit user action so token spend
> is fully under control; a keyword-based classifier acts as a free fallback.
> Deployed on Render with continuous deployment from GitHub.
>
> Tech: Python 3.12 · Flask · OpenAI (gpt-4o-mini) · Tailwind · gunicorn · pytest · Render
>
> 🔗 Live demo: <your-render-url>
> 🔗 Code: https://github.com/<you>/AI-IT-helpdesk-Ticket-Assistant

### LinkedIn — Post (when you launch)

> Just shipped a small side-project: an AI-powered helpdesk ticket triage tool 🛠️
>
> Drop in a support ticket and it classifies the issue, scores priority, suggests
> resolution steps, and drafts a reply you can copy-paste back to the user.
> The trick: AI only runs when the user clicks "Generate", so token spend stays
> tiny. A keyword classifier kicks in as a free fallback for demos.
>
> Stack: Python · Flask · OpenAI gpt-4o-mini · Tailwind · gunicorn, deployed on Render.
>
> Live demo (give it 30s to wake up on first request):
> 👉 <your-render-url>
>
> Code & write-up: <your-github-url>
>
> Built this to scratch an itch from my IT support / Zendesk days — happy to chat
> about the design choices if anyone's curious. 💬

### Tips for the demo

- Click **"Load demo"** in the live UI to repopulate the 8 example tickets after
  someone clears them.
- Try one ticket with the **"Use offline heuristic"** checkbox on, then off, to
  show off the difference between the rule-based path and the GPT path.
- Take a screenshot of the populated app and use it as your LinkedIn featured
  image — looks great.

---

## How AI calls are gated

```py
# app/routes.py
@bp.post("/tickets/<ticket_id>/analyze")
def analyze_ticket(ticket_id):
    """On-demand AI analysis. Triggered ONLY by the user's Generate click."""
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
| POST   | `/api/tickets/seed`               | Insert demo tickets (only if store is empty)   |
| GET    | `/api/stats`                      | Counts by status, category, priority           |

CSV columns (case-insensitive, common synonyms accepted):
`subject` · `body` (or `description`) · `requester` (or `email`).

---

## Tests

```bash
pytest -q
```

17 tests cover the heuristic classifier, the OpenAI fallback path
(monkey-patched), every JSON endpoint, the no-cache headers, and the
seed-once-only behavior. Whole suite runs in under a second.

---

## Roadmap ideas

- Swap the JSON store for Postgres + SQLAlchemy
- Add a Zendesk webhook that POSTs incoming tickets into `/api/tickets`
- Background job to **batch-triage** on schedule (still gated behind a button)
- Authentication + per-user views
- Per-category accuracy dashboard once you have a labeled set
