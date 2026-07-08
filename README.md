# Triagent — AI ticket triage, on demand

> An AI-powered IT helpdesk triage assistant. Drop in a ticket → click **Generate** →
> get a category, priority, suggested resolution steps, and a ready-to-send reply
> draft. AI calls fire **only** on click, so it stays cheap (or free) to run.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

For each ticket Triagent will:

1. **Classify** the issue (network · login · hardware · software · email · access · billing · other)
2. **Score priority** (low / medium / high / urgent)
3. **Suggest concrete resolution steps**
4. **Draft a polite, ready-to-send reply** to the requester

> **Resume line:** *Designed and shipped Triagent — an AI-powered IT helpdesk
> ticket triage tool that classifies, prioritizes, and drafts replies on demand
> using GPT-4o-mini, with a keyword-heuristic fallback that keeps the live demo
> running on $0 of API spend.*

---

## Why Triagent is cheap to run

- AI is **only invoked when the user clicks "Generate AI triage"** on a specific
  ticket. No background calls, no per-keystroke calls, no auto-classification on
  upload.
- A keyword **heuristic fallback** runs instantly and locally when no
  `OPENAI_API_KEY` is set, so the whole demo works on **0 credits**.
- A per-call **"offline"** toggle in the UI lets you triage without spending
  tokens once a key is configured.

---

## Stack

- **Backend:** Python 3.12 · Flask 3 · SQLAlchemy 2 · OpenAI SDK · gunicorn
- **Storage:** **Neon Postgres** in production (serverless, free forever, autosuspend/wake), SQLite locally (zero-config; just `python wsgi.py`)
- **Frontend:** single-page HTML + Tailwind (CDN) + vanilla JS — no build step
- **Tests:** 27 pytest tests against an in-test SQLite, all run in <2s
- **Deploy:** one-click to Render (free web service) + Neon (free serverless Postgres) — both free forever, `render.yaml` provisions the web service and expects `DATABASE_URL` set to your Neon connection string

```
.
├── app/
│   ├── __init__.py     # Flask factory
│   ├── routes.py       # /api/* endpoints
│   ├── ai.py           # OpenAI call + heuristic fallback
│   ├── seed.py         # Optional demo data on first boot
│   └── storage.py      # JSON ticket store + CSV parser
├── frontend/
│   ├── index.html      # Triagent UI shell (Tailwind)
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

Open Triagent, click **+ New ticket** (or upload `frontend/sample_tickets.csv`),
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

This repo includes a `render.yaml`, so Render auto-configures everything and
your service ends up at **`https://triagent.onrender.com`** (or
`https://triagent-<random>.onrender.com` if `triagent` is taken; you can rename
later in Settings).

### Steps

1. **Push the code to your own GitHub repo** (it's already there if you cloned this one).
2. Sign up at [render.com](https://render.com) — you can sign in with GitHub. **No credit card required for the free tier.**
3. Click **New → Blueprint** → **Connect** the GitHub repo.
4. Render reads `render.yaml`, names the service `triagent`, and shows you the env vars it'll create.
5. Set two env vars in the Render dashboard:
   - `OPENAI_API_KEY` = your `sk-...` (or leave blank to run in free heuristic mode)
   - `DATABASE_URL` = your Neon connection string (see below to grab one for free)
6. Click **Apply**. First build takes ~3 minutes.
7. You'll get a public URL like `https://triagent.onrender.com`.

That's it — Triagent is online with HTTPS, auto-deploys on every push to `main`, and seeds 8 example tickets on first boot so visitors immediately see something useful.

### Get a free Neon Postgres (2 min)

Render's own free Postgres tier auto-deletes after ~90 days of inactivity, which will nuke a portfolio demo overnight. Use [Neon](https://neon.tech) instead — free 3 GB Postgres that autosuspends when idle and wakes on first request, no expiry.

1. Sign up at https://console.neon.tech with GitHub — no card required.
2. **Create Project** → name it `triagent` → region close to your Render service (US East works well with Render's Oregon region too).
3. On the project page, click **"Connection Details"** or **"Connection String"** → copy the URL (starts with `postgresql://`).
4. Paste it as `DATABASE_URL` in Render → Environment.
5. Redeploy the Render service. The app runs `Base.metadata.create_all()` on boot, so the tables get created automatically.

### Free tier tradeoffs (totally fine for a portfolio demo)

- The Render web service spins down after 15 minutes of inactivity → ~30s cold start on next visit (the frontend shows a "waking server" hint).
- Neon Postgres autosuspends after ~5 minutes idle → adds ~1s to the first request. `pool_pre_ping=True` in `app/db.py` transparently retries the stale connection so users never see an error.
- Accounts and tickets persist forever — no 90-day expiry, unlike Render's own free Postgres 🎉
- Add this line to your README: *"Live demo: https://triagent-n3ok.onrender.com (first request may take 30s to wake)."*

### Custom domain (optional, ~$10/year)

Want `triagent.dev` or `helpdesk.ayushgokani.com`? Buy the domain from Cloudflare Registrar or Namecheap, then in Render: your service → **Settings** → **Custom Domains** → **Add Custom Domain** → follow the CNAME instructions. Render auto-issues a free HTTPS certificate. No extra hosting cost.

### Other hosts

The included `Procfile` works on **Heroku** and **Railway** too:

```
web: gunicorn wsgi:app --workers 2 --bind 0.0.0.0:$PORT --timeout 60
```

Just set the same env vars (`OPENAI_API_KEY`, `FLASK_SECRET_KEY`, `OPENAI_MODEL`, `SEED_DEMO_DATA=1`) in their dashboards.

---

## Putting Triagent on your resume & LinkedIn

### Resume — short bullet (1 line)

> **Triagent** — Python · Flask · OpenAI · Tailwind SPA · Render
> Built and deployed an AI-powered IT helpdesk ticket triage tool that classifies, prioritizes, and drafts replies on demand using GPT-4o-mini, with a keyword-heuristic fallback for zero-credit demos.

### Resume — fuller version (3 bullets)

**Triagent — AI Helpdesk Ticket Assistant** | *Personal project* | [Live demo](https://triagent.onrender.com) · [GitHub](https://github.com/AyushGokani/AI-IT-helpdesk-Ticket-Assistant)
- Designed and shipped a full-stack IT support triage tool (Python · Flask · OpenAI SDK · vanilla JS / Tailwind SPA), deployed on Render with auto-deploy CI on every push.
- Engineered an **on-demand-only** AI architecture so token spend is gated behind a single user action, with a keyword-classifier fallback that keeps the app fully functional on $0 of API credit.
- Built REST API for ticket CRUD, CSV bulk import, classification, priority scoring, and reply drafting; **17 pytest tests** cover the API and both AI paths (LLM + heuristic).

### LinkedIn — Featured / Project section

**Title:** Triagent — AI Helpdesk Ticket Assistant
**Description (paste this):**

> Triagent is an AI-powered triage tool for IT support tickets. Upload a ticket
> and the app classifies the issue (network / login / hardware / etc.), assigns
> a priority, suggests concrete resolution steps, and drafts a ready-to-send
> reply to the requester — all with one click.
>
> Built with Python (Flask) on the backend and a single-page Tailwind + vanilla
> JS frontend. AI calls are gated behind an explicit user action so token spend
> is fully under control; a keyword-based classifier acts as a free fallback.
> Deployed on Render with continuous deployment from GitHub.
>
> Tech: Python 3.12 · Flask · SQLAlchemy · **Neon Postgres** · OpenAI (gpt-4o-mini) · Resend · Tailwind · gunicorn · pytest · Render
>
> 🔗 Live demo: https://triagent.onrender.com
> 🔗 Code: https://github.com/AyushGokani/AI-IT-helpdesk-Ticket-Assistant

### LinkedIn — Launch post

> Just shipped a side-project: **Triagent**, an AI-powered helpdesk ticket triage tool 🛠️
>
> Drop in a support ticket and it classifies the issue, scores priority, suggests
> resolution steps, and drafts a reply you can copy-paste back to the user.
>
> The design choice I'm proud of: AI **only** runs when the user clicks "Generate",
> so token spend stays tiny — and a keyword classifier kicks in as a free fallback
> for demos. Means the live URL works for anyone visiting without me burning credits.
>
> Stack: Python · Flask · SQLAlchemy · **Neon Postgres** · OpenAI gpt-4o-mini · Resend · Tailwind · gunicorn, deployed on Render.
>
> Built this to scratch an itch from my IT support / Zendesk days. Happy to chat
> about the design choices if anyone's curious. 💬
>
> 👉 Live demo (give it 30s to wake up on first request): https://triagent.onrender.com
> 👉 Code: https://github.com/AyushGokani/AI-IT-helpdesk-Ticket-Assistant

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

## Auth & per-user data

Every visitor needs a free account before they can use Triagent. Sessions use
Flask's signed cookies (`HttpOnly`, `SameSite=Lax`, plus `Secure` in production
when `SESSION_COOKIE_SECURE=1`). Passwords are hashed with PBKDF2 via Werkzeug.

Tickets are scoped per user — Alice never sees Bob's queue, and the API
returns `404` (not `403`) on cross-account access so it doesn't even leak that
a ticket exists.

When `SEED_DEMO_DATA=1`, each new signup is auto-populated with 8 demo tickets
so the first login isn't an empty inbox.

### Forgot password / reset by email

`Forgot password?` link on the sign-in screen kicks off a 3-step flow:

1. User enters their email → backend issues a **6-digit code**, hashes it,
   stores it with a 15-minute TTL, and emails the plaintext to the user.
2. User enters the code → server validates without consuming it.
3. User picks a new password → server verifies the code one last time,
   updates the password hash, marks the code used, and signs the user in.

Codes are **single-use**, **expire in 15 minutes**, and **lock after 5 wrong
attempts**. Issuing a new code invalidates any earlier unused one. The
`/forgot-password` endpoint always returns a generic success message so it
can't be used to enumerate which emails have accounts.

#### Email backends

The email sender picks the first configured backend automatically:

| Backend         | Set these env vars                                                  | Notes                              |
| --------------- | ------------------------------------------------------------------- | ---------------------------------- |
| **Gmail SMTP**  | `SMTP_HOST=smtp.gmail.com` `SMTP_PORT=587` `SMTP_USER` `SMTP_PASSWORD` | Use a [Gmail App Password](https://myaccount.google.com/apppasswords), not your account password |
| **Resend**      | `RESEND_API_KEY=re_...`                                             | Free 100 emails/day, sign up with GitHub at resend.com |
| **Console**     | (none)                                                              | Fallback — prints the email to stdout. Visible in `python wsgi.py` terminal locally, or in Render logs in production. |

For the live demo the console fallback is fine — show the demo, point at
"check Render logs to see the code", and that's a real working flow.

## API

### Auth (no auth required)

| Method | Path                          | What it does                                                            |
| ------ | ----------------------------- | ----------------------------------------------------------------------- |
| POST   | `/api/auth/signup`            | `{email, password, name?}` → creates user, logs in, seeds demo data     |
| POST   | `/api/auth/login`             | `{email, password}`                                                     |
| POST   | `/api/auth/logout`            | Clears the session                                                      |
| GET    | `/api/auth/me`                | `{user}` or `{user: null}`                                              |
| PATCH  | `/api/auth/me`                | `{name}` (login required)                                               |
| POST   | `/api/auth/change-password`   | `{current_password, new_password}` (login required)                     |
| POST   | `/api/auth/forgot-password`   | `{email}` → emails a 6-digit reset code (always returns generic 200)    |
| POST   | `/api/auth/verify-reset-code` | `{email, code}` → validates the code without consuming it               |
| POST   | `/api/auth/reset-password`    | `{email, code, new_password}` → sets new password and auto-logs you in  |
| GET    | `/api/health`                 | Public — reports whether an API key is configured                       |

### Tickets (login required, scoped to current user)

| Method | Path                              | What it does                                   |
| ------ | --------------------------------- | ---------------------------------------------- |
| GET    | `/api/tickets`                    | List your tickets (newest first)               |
| POST   | `/api/tickets`                    | Create a ticket `{subject, body, requester?}`  |
| GET    | `/api/tickets/<id>`               | Get one ticket                                 |
| POST   | `/api/tickets/<id>/analyze`       | **Run AI triage** (`{"offline": true}` to force heuristic) |
| POST   | `/api/tickets/<id>/status`        | Update status `{open, in_progress, resolved}`  |
| DELETE | `/api/tickets/<id>`               | Delete                                         |
| POST   | `/api/tickets/upload`             | Bulk upload CSV (multipart `file`)             |
| POST   | `/api/tickets/clear`              | Wipe your tickets                              |
| POST   | `/api/tickets/seed`               | Insert demo tickets (only if your queue is empty) |
| GET    | `/api/stats`                      | Counts by status, category, priority           |

CSV columns (case-insensitive, common synonyms accepted):
`subject` · `body` (or `description`) · `requester` (or `email`).

---

## Tests

```bash
pytest -q
```

36 tests cover signup/login/logout, password hashing & changes, per-user data
isolation (Alice can't see Bob's tickets), the **full forgot-password flow**
(code generation, single-use semantics, expiry, max-attempts lockout, code
rotation), the heuristic classifier, the OpenAI fallback path (monkey-patched),
every JSON endpoint, the no-cache headers, and the seed-once-only behavior.
Whole suite runs in under five seconds.

---

## Roadmap ideas

- Swap the JSON store for Postgres + SQLAlchemy
- Add a Zendesk webhook that POSTs incoming tickets into `/api/tickets`
- Background job to **batch-triage** on schedule (still gated behind a button)
- Authentication + per-user views
- Per-category accuracy dashboard once you have a labeled set

---

Built with care by [Ayush Gokani](https://github.com/AyushGokani).
