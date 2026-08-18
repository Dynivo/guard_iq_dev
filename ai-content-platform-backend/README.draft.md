# AI Content Intelligence Platform — Backend

FastAPI modular monolith for LinkedIn content intelligence: news fetch → screen → draft → review → assets.

This README is the **client handoff guide**. After reading it you should be able to install dependencies, configure `.env`, run the API, and verify the system.

| Doc | Purpose |
|-----|---------|
| [`.env.example`](.env.example) | Every env var with Required / Optional / Conditional notes |
| [`docs/architecture/LOCAL_AND_SERVER_SETUP.md`](docs/architecture/LOCAL_AND_SERVER_SETUP.md) | Cloud/server notes |
| [`docs/architecture/SOFTWARE_ARCHITECTURE_v3.2.md`](docs/architecture/SOFTWARE_ARCHITECTURE_v3.2.md) | Architecture source of truth |

There is **no LinkedIn auto-post**. Editors approve drafts and publish manually.

---

## Quick start (local, no paid API keys)

The common path in one block. Every command is explained in the sections below if something doesn't work.

```bash
cd ai-content-platform-backend

# 1. Python environment
python3 -m venv .venv
source .venv/bin/activate          # macOS/Linux — Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Database (needs Postgres 14+ already installed and running)
createdb ai_content_platform

# 3. Configure
cp .env.example .env
# Edit .env: set JWT_SECRET_KEY / JWT_REFRESH_SECRET_KEY to random values
#   python -c "import secrets; print(secrets.token_hex(32))"
# Everything else can stay at its default (mock LLM, mock images, inline jobs)

# 4. Set up the database and seed starter data
alembic upgrade head
python scripts/seed_database.py

# 5. Run
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Log in at `admin@guardiq.com` / `Admin123!` (change this before going live). Health check: http://127.0.0.1:8000/api/v1/health. API docs: http://127.0.0.1:8000/docs.

That's the whole install. Redis and a background worker are **not required** — see [§7](#7-background-worker-dramatiq--when-and-why) for when you'd want them.

---

## What the app does

### News ingest and relevance screening

Sources (RSS feeds or news APIs — 46 seeded by default) are configured on the **Sources** page, each with an optional cron schedule. A background loop (`SOURCE_CRON_ENABLED`, on by default) checks every `SOURCE_CRON_INTERVAL_SECONDS` for sources whose schedule is due and fetches them, staggered (`SOURCE_CRON_MAX_DISPATCH_PER_SWEEP`) so a fresh install's sources don't all fire at once. Sources can also be run manually. Each run is capped at `MAX_ARTICLES_PER_SOURCE_RUN` new articles and de-duplicated by URL. Manual run-all and screening priority put the original GuardIQ sources first: NCSC, Microsoft Security Response Center, then The Hacker News.

**Ingest itself never calls an LLM.** New articles land in a queue (status `scored`) and cost nothing until someone screens them. Screening is a deliberate, user-triggered batch:

- **"Screen next 100"** — scores up to 100 never-screened articles.
- **"Rescore relevant"** — re-screens up to 100 of the least-recently-scored relevant articles (useful after tuning the brand profile or prompt).
- A single article can also be rescored individually.
- `/api/v1/articles/screening-status` reports how many are queued/in progress, so the UI can show a live progress bar.

The LLM receives the title, source, date, summary, and up to 3,000 characters of available article body. It returns a binary **relevant** or **rejected** decision plus a 1–5 score, sector, framework, and plain-English reason. Scores 3–5 can be relevant when all four relevance tests pass; deterministic editorial guards still reject stale, thin, duplicate, or already-drafted stories. The audience is UK regulated firms of 5–70 people, and global stories qualify when the lesson clearly transfers.

Editors can override any call with a thumbs Yes/No — this is the only path that durably teaches the system: it records a `WritingPreference`, optionally a `Rule`, and appends to the org's brand-profile Markdown.

**Housekeeping:** an `irrelevant` article is permanently deleted once it's `IRRELEVANCE_ARTICLE_RETENTION_DAYS` old (default 1) unless a draft still references it — swept hourly, disabled by setting the value to `0`. A `relevant` article can instead be **hidden** from the default feed without touching its classification or deleting it — useful for decluttering without losing the signal.

### Drafts and review

LinkedIn posts are generated from a relevant article (News) or from the user's own story (Capture — voice or text). Drafts move through `pending_review → approved/rejected`, can be rewritten (whole post, or just the hook/body/CTA), and support inline images.

### Image generation

Two variants can be generated per draft, both via Gemini/OpenAI: a text-forward "blue card" and an infographic-style "white card". For both, the real brand logo is sent to the model **as a reference image** so it's placed natively in the composition, with deterministic pixel-compositing only as a fallback for providers/cases that can't consume a reference. An optional house-style exemplar (`assets/brand/style_reference.png`, `.jpg`, or `.webp`) is sent alongside as a visual reference so output stays consistent with an approved look — if the file isn't present, generation proceeds on the text prompt alone. How many images generate by default, and whether one queues automatically alongside the draft, are both configured on the Brand Kit (`extra_settings.default_image_count`, `extra_settings.auto_generate_image_with_draft`).

### Publishing Plan

The Plan page tracks a weekly or fortnightly content mix (educational / success-story / personal-achievement targets, set on the Brand Kit). Two different counts matter here:

- **What's actually planned** (`counts`/`gaps`) — a draft only counts once it is **both approved and given a date**. This is exactly what's on the calendar.
- **What's in the pipeline** (`pipeline_counts`/`generation_gaps`) — every draft in flight for the window, including ones still awaiting review. **Auto Generate** gates on this number, not the first one, so it won't write duplicate drafts while earlier ones sit unreviewed.

**Seed calendar** assigns approved-but-undated drafts onto workdays, respecting the mix targets. **Clear calendar** unschedules everything (drafts themselves are untouched, just the date is removed).

### Diagnostics export

Settings has a "Download diagnostics" button (`GET /api/v1/diagnostics/export`) that bundles recent job history, environment info, and a tail of the on-disk log into a zip — meant to be emailed when something breaks. The log tail is redacted before bundling: every configured provider/JWT/database secret is stripped by exact match, and anything shaped like a credential in a URL query string (`?key=...`, `?token=...`) is stripped by pattern, so a provider SDK logging a request URL with the key embedded can't leak it.

### Also present

Brief pointers — these exist and are functional, but aren't documented in depth here:

- **Capture** — turn a voice recording or typed story into a draft (Success / Personal Achievement).
- **Brand Intelligence** — a 12-step wizard that imports LinkedIn/website/assets and produces writing- and visual-DNA scores.
- **Learning** — the durable examples/rules/preferences records built up from approvals, rejections, and relevance overrides.
- **Consensus** — optional multi-LLM draft scoring (`CONSENSUS_ENABLED`), picks the best of several generated drafts.
- **Carousels / Typography** — multi-slide export and text-overlay compositing for images.

---

## Prerequisites (checklist)

| Component | Required? | Purpose |
|-----------|-----------|---------|
| Python **3.11+** | Yes | Backend runtime |
| PostgreSQL **14+** | Yes | App database |
| Redis | Only if `JOB_BACKEND=dramatiq` | Job queue |
| LLM API key(s) | Optional | Real text generation (`mock` works without keys) |
| Image provider | Optional | Real images (`mock` / `openai` / `comfyui`) |

---

## 1. Clone and Python environment

```bash
cd ai-content-platform-backend

python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

pip install -r requirements.txt
```

Optional health check: `bash scripts/setup.sh` (or `powershell scripts/setup.ps1` on Windows).

---

## 2. PostgreSQL setup

The app expects a database named **`ai_content_platform`**.

### Option A — Local PostgreSQL (macOS Homebrew)

```bash
brew install postgresql@16
brew services start postgresql@16
createuser -s postgres 2>/dev/null || true
createdb ai_content_platform
```

**`.env` value:**

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ai_content_platform
```

### Option B — Local PostgreSQL (Ubuntu / Debian server)

```bash
sudo apt update
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

sudo -u postgres psql -c "CREATE USER appuser WITH PASSWORD 'strongpassword';"
sudo -u postgres psql -c "CREATE DATABASE ai_content_platform OWNER appuser;"
```

**`.env` value:**

```env
DATABASE_URL=postgresql+asyncpg://appuser:strongpassword@127.0.0.1:5432/ai_content_platform
```

### Option C — Remote Postgres (AWS RDS / managed)

1. Create instance and allow your laptop / server IP on port **5432**.
2. Create the database:

```bash
PGPASSWORD='YOUR_PASSWORD' psql \
  "host=YOUR_RDS_HOST port=5432 user=postgres dbname=postgres sslmode=require" \
  -c "CREATE DATABASE ai_content_platform;"
```

3. Set in `.env`:

```env
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@YOUR_RDS_HOST:5432/ai_content_platform
DATABASE_SSL=require
# Optional but recommended for RDS:
# DATABASE_SSL_CA=/path/to/global-bundle.pem
```

**Note:** Do **not** put `sslmode=require` inside the asyncpg `DATABASE_URL`. Use `DATABASE_SSL` instead.

---

## 3. Environment file (`.env`)

```bash
cp .env.example .env
```

**Minimum to boot locally with mocks (no paid APIs):**

| Variable | Example | Notes |
|----------|---------|--------|
| `DATABASE_URL` | see Postgres section | **Required** |
| `JWT_SECRET_KEY` | long random hex | **Required** (change from placeholder) |
| `JWT_REFRESH_SECRET_KEY` | different long random hex | **Required** |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Must match frontend URL |
| `JOB_BACKEND` | `inline` | No worker needed |
| `DEFAULT_LLM_PROVIDER` | `mock` | No LLM keys needed |
| `IMAGE_PROVIDER` | `mock` | No image API / GPU needed |
| `STORAGE_PROVIDER` | `local` | Files under `data/media` |

Generate secrets:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Full field list:** see [`.env.example`](.env.example) — every variable is documented there.

### Turning on real AI / images (optional)

| Goal | Set these |
|------|-----------|
| Real LinkedIn drafts | `DEFAULT_LLM_PROVIDER=openai` (or `gemini` / …) + matching `*_API_KEY` |
| OpenAI images | `IMAGE_PROVIDER=openai` + `OPENAI_API_KEY` + `OPENAI_IMAGE_MODEL=gpt-image-1` |
| ComfyUI images | `IMAGE_PROVIDER=comfyui` + ComfyUI running + `COMFYUI_BASE_URL` |
| Background jobs | `JOB_BACKEND=dramatiq` + Redis + separate worker (§7) |

Generated images are always written to local disk under `STORAGE_LOCAL_ROOT` (default `data/media`).

---

## 4. Database migrations + seed

```bash
alembic upgrade head
python scripts/seed_database.py
```

This seeds the GuardIQ org, an admin user, a brand kit (with sensible `extra_settings` defaults so a re-seed doesn't silently disable things you'd already configured), 46 starter news sources, provider configs, and a couple of example claims.

**Default login after seed:** `admin@guardiq.com` / `Admin123!`. Change this password before going live.

---

## 5. Run the API server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| Check | How |
|-------|-----|
| Health | http://127.0.0.1:8000/api/v1/health |
| OpenAPI docs | http://127.0.0.1:8000/docs |
| Login | `POST /api/v1/auth/login` with seed credentials |

Leave this terminal running while you use the frontend.

---

## 6. Resetting to a clean install

To wipe all data and go back to a fresh-install state (org, admin login, brand kit, sources — no articles/drafts/history):

```bash
# Inside a psql session or a short script, truncate every app table except alembic_version, then:
python scripts/seed_database.py
```

Media files under `data/media/` are separate from the database — clear that directory too if you want generated images gone as well. This does **not** touch anything git-tracked (prompts, brand profile, house-style reference image), so a reset doesn't lose tuning that lives in code/config — only what was ever database-only state (e.g. an uploaded logo, accumulated learning preferences).

---

## 7. Background worker (Dramatiq) — when and why

| Mode | `JOB_BACKEND` | Behaviour |
|------|---------------|-----------|
| **Inline** (default) | `inline` | Fetch / screen / image jobs run **inside** the API process. Simple for local use. |
| **Dramatiq** | `dramatiq` | API only **enqueues** jobs to Redis. A **separate worker process** executes them. For production / heavier load. |

Set in `.env`:

```env
JOB_BACKEND=dramatiq
REDIS_URL=redis://localhost:6379/0
```

Then, in a second terminal:

```bash
cd ai-content-platform-backend
source .venv/bin/activate
bash scripts/run_worker.sh
```

**Important:** the entrypoint is `dramatiq app.workers` — not `app.modules.jobs`. If `JOB_BACKEND=dramatiq` but no worker is running, jobs stay queued and never finish. If `JOB_BACKEND=inline`, you don't need a worker at all.

### Redis setup (only if using Dramatiq)

```bash
brew install redis && brew services start redis        # macOS
# or: sudo apt install -y redis-server && sudo systemctl enable --now redis-server
redis-cli ping    # expect: PONG
```

---

## 8. Verification checklist

- [ ] `alembic upgrade head` completed without errors
- [ ] `python scripts/seed_database.py` created the admin user
- [ ] http://127.0.0.1:8000/api/v1/health returns OK
- [ ] http://127.0.0.1:8000/docs loads
- [ ] Login works with `admin@guardiq.com` / `Admin123!`
- [ ] Frontend `VITE_API_BASE_URL` points here and `CORS_ORIGINS` includes the frontend origin
- [ ] If `JOB_BACKEND=dramatiq`: worker log shows Dramatiq started; Sources → Run completes a job

---

## 9. Command cheat sheet

| Command | Purpose |
|---------|---------|
| `python3 -m venv .venv` | Create virtualenv |
| `source .venv/bin/activate` | Activate virtualenv |
| `pip install -r requirements.txt` | Install dependencies |
| `cp .env.example .env` | Create local secrets file |
| `createdb ai_content_platform` | Create Postgres database (local) |
| `alembic upgrade head` | Apply DB migrations |
| `python scripts/seed_database.py` | Seed org / admin / sources |
| `uvicorn app.main:app --reload --port 8000` | Start API |
| `bash scripts/run_worker.sh` | Start background workers (Dramatiq only) |
| `redis-cli ping` | Check Redis (Dramatiq only) |
| `pytest` | Run tests |

---

## 10. Project structure (short)

```text
app/
  api/             HTTP routes, schemas, middleware
  core/            Settings, JWT, logging, constants
  modules/         Domain modules (news, content, intelligence, image, capture, …)
  infrastructure/  Postgres, Redis, LLM/image adapters, connectors
  workers/         Dramatiq actors (background jobs)
  main.py          API entrypoint
configs/           YAML prompts, brand, workflows, providers
assets/brand/      Logo + optional house-style reference image
scripts/           seed, worker, setup helpers
alembic/           Migrations
tests/             Unit / integration tests
```

---

## 11. API surface (starter)

All JSON under `/api/v1/` (see `/docs` for the full list).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/health` | No | Liveness |
| POST | `/api/v1/auth/login` | No | Email / password → tokens |
| POST | `/api/v1/auth/refresh` | No | Refresh access token |
| GET | `/api/v1/auth/me` | Yes | Current user |
| GET | `/api/v1/articles` | Yes | News feed |
| POST | `/api/v1/articles/rescore-new` | Yes | Screen up to 100 unscored articles |
| POST | `/api/v1/articles/rescore-relevant` | Yes | Re-screen up to 100 relevant articles |
| GET | `/api/v1/articles/screening-status` | Yes | Live screening queue/progress |
| GET | `/api/v1/sources` | Yes | News sources |
| GET | `/api/v1/drafts` | Yes | Draft list |
| GET | `/api/v1/publishing-plan` | Yes | Mix targets, counts, calendar gaps |
| GET | `/api/v1/diagnostics/export` | Yes | Download a redacted diagnostics zip |

Envelope shape: `{ "data": ..., "error": ..., "meta": { "request_id": "..." } }`

---

## 12. Production notes (short)

1. Set `APP_ENV=production`, `APP_DEBUG=false`, strong JWT secrets.
2. Prefer `JOB_BACKEND=dramatiq` + Redis + a process manager (systemd, launchd, etc.) for API **and** worker.
3. Use managed Postgres (RDS) + `DATABASE_SSL=require`.
4. Point `CORS_ORIGINS` at the real frontend origin only.
5. Never commit `.env`. Rotate any leaked keys.
6. More detail: [`docs/architecture/LOCAL_AND_SERVER_SETUP.md`](docs/architecture/LOCAL_AND_SERVER_SETUP.md).

---

## Support paths

| Issue | Likely fix |
|-------|------------|
| DB connection refused | Start Postgres; check `DATABASE_URL` host/port/password |
| RDS SSL / auth errors | `DATABASE_SSL=require`; security group allows your IP |
| Jobs stuck in "queued" | Set `JOB_BACKEND=inline` **or** start `bash scripts/run_worker.sh` |
| CORS errors in browser | Add exact frontend origin to `CORS_ORIGINS` |
| Mock-looking posts/images | Set real `DEFAULT_LLM_PROVIDER` / `IMAGE_PROVIDER` + keys |
| Nothing in News is relevant | Click "Screen next 100"; improve the Brand profile Markdown; use Yes/No to teach it |
| Worker crashes on import | Activate `.venv`; run from repo root; use `dramatiq app.workers` |
| Diagnostics export won't download | Check the API log at `logs/app.log` directly — the export needs the app running |
