# AI Content Intelligence Platform — Backend

FastAPI modular monolith for LinkedIn content intelligence: news fetch → score → draft → review → assets.

This README is the **client handoff guide**. After reading it you should be able to install dependencies, configure `.env`, run the API, optionally run workers, and verify the system.

| Doc | Purpose |
|-----|---------|
| [`.env.example`](.env.example) | Every env var with Required / Optional / Conditional notes |
| [`docs/architecture/LOCAL_AND_SERVER_SETUP.md`](docs/architecture/LOCAL_AND_SERVER_SETUP.md) | Contabo / Vercel / cloud notes |
| [`docs/architecture/SOFTWARE_ARCHITECTURE_v3.2.md`](docs/architecture/SOFTWARE_ARCHITECTURE_v3.2.md) | Architecture source of truth |

---

## What you are running

| Process | Role |
|---------|------|
| **API** (`uvicorn`) | HTTP REST API the frontend calls (`/api/v1/...`) |
| **Worker** (`dramatiq`, optional) | Background jobs: news ingest, scoring, image batches |
| **PostgreSQL** | Primary database (users, articles, drafts, brand, jobs) |
| **Redis** | Job broker + optional cache (needed for Dramatiq workers) |

There is **no LinkedIn auto-post**. Editors approve drafts and publish manually.

---

## Prerequisites (checklist)

| Component | Required? | Purpose |
|-----------|-----------|---------|
| Python **3.11+** | Yes | Backend runtime |
| PostgreSQL **14+** | Yes | App database |
| Redis | Recommended (required if `JOB_BACKEND=dramatiq`) | Job queue / cache |
| LLM API key(s) | Yes for AI features | Text generation and scoring |
| Image provider credentials | Yes for cloud images | Gemini / OpenAI key, or self-hosted ComfyUI |

---

## 1. Clone and Python environment

```bash
cd ai-content-platform-backend

# Create an isolated Python environment
python3 -m venv .venv

# Activate it (run this in every new terminal)
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows PowerShell

# Install Python packages
pip install -r requirements.txt
```

| Command | What it does |
|---------|----------------|
| `python3 -m venv .venv` | Creates a private Python install in `.venv/` |
| `source .venv/bin/activate` | Puts that Python/pip on your PATH for this shell |
| `pip install -r requirements.txt` | Installs FastAPI, SQLAlchemy, Dramatiq, etc. |

Optional health check: `bash scripts/setup.sh` (or `powershell scripts/setup.ps1` on Windows).

---

## 2. PostgreSQL setup

The app expects a database named **`ai_content_platform`**.

### Option A — Local PostgreSQL (macOS Homebrew)

```bash
# Install
brew install postgresql@16
brew services start postgresql@16

# Create role/db if needed (adjust user/password to match your .env)
createuser -s postgres 2>/dev/null || true
createdb ai_content_platform

# Or via psql:
psql postgres -c "CREATE DATABASE ai_content_platform;"
```

| Command | What it does |
|---------|----------------|
| `brew services start postgresql@16` | Starts Postgres in the background |
| `createdb ai_content_platform` | Creates the empty application database |

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

1. Create instance and allow your laptop / server IP on port **5432** (security group / firewall).
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

## 3. Redis setup

Redis is **required** when `JOB_BACKEND=dramatiq`. It is still useful with `inline` jobs.

### macOS

```bash
brew install redis
brew services start redis
redis-cli ping    # expect: PONG
```

### Ubuntu / Debian

```bash
sudo apt install -y redis-server
sudo systemctl enable --now redis-server
redis-cli ping    # expect: PONG
```

### `.env`

```env
REDIS_URL=redis://localhost:6379/0
```

| Command | What it does |
|---------|----------------|
| `brew services start redis` / `systemctl start redis-server` | Starts Redis daemon |
| `redis-cli ping` | Confirms Redis is reachable |

---

## 4. Environment file (`.env`)

```bash
cp .env.example .env
# Edit .env — set DATABASE_URL, JWT secrets, and any API keys you need
```

**Minimum local configuration:**

| Variable | Example | Notes |
|----------|---------|--------|
| `DATABASE_URL` | see Postgres section | **Required** |
| `JWT_SECRET_KEY` | long random hex | **Required** (change from placeholder) |
| `JWT_REFRESH_SECRET_KEY` | different long random hex | **Required** |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Must match frontend URL |
| `JOB_BACKEND` | `inline` | No worker needed |
| `DEFAULT_LLM_PROVIDER` | `gemini` | Set the matching provider API key |
| `IMAGE_PROVIDER` | `gemini` | Set `GEMINI_API_KEY`, or configure another real image provider |
| `STORAGE_PROVIDER` | `local` | Files under `data/media` |

Generate secrets:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Full field list (required / optional / conditional):** see [`.env.example`](.env.example) — every variable is documented there.

### Turning on real AI / images (optional)

| Goal | Set these |
|------|-----------|
| Real LinkedIn drafts | `DEFAULT_LLM_PROVIDER=openai` (or `gemini` / …) + matching `*_API_KEY` |
| OpenAI images | `IMAGE_PROVIDER=openai` + `OPENAI_API_KEY` + `OPENAI_IMAGE_MODEL=gpt-image-1` |
| ComfyUI images | `IMAGE_PROVIDER=comfyui` + ComfyUI running + `COMFYUI_BASE_URL` |
| Background jobs | `JOB_BACKEND=dramatiq` + Redis + **separate worker** (next section) |

Generated images (original / optimized / thumbnail) are always written to local disk under `STORAGE_LOCAL_ROOT` (default `data/media`).


---

## 5. Database migrations + seed

With venv active and Postgres running:

```bash
# Apply schema migrations (creates / updates tables)
alembic upgrade head

# Seed org, admin user, brand kit, default news sources
python scripts/seed_database.py
```

| Command | What it does |
|---------|----------------|
| `alembic upgrade head` | Runs all pending SQL migrations |
| `python scripts/seed_database.py` | Inserts GuardIQ org, admin, sources, provider configs |

**Default login after seed**

- Email: `admin@guardiq.com`
- Password: `Admin123!`

Change this password in production.

---

## 6. Run the API server

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| Flag | Meaning |
|------|---------|
| `app.main:app` | FastAPI application object |
| `--reload` | Auto-restart on code changes (dev only) |
| `--host 127.0.0.1` | Local only; use `0.0.0.0` if other machines must reach it |
| `--port 8000` | HTTP port |

**Check it works**

| Check | How |
|-------|-----|
| Health | Open http://127.0.0.1:8000/api/v1/health |
| OpenAPI docs | http://127.0.0.1:8000/docs |
| Login | `POST /api/v1/auth/login` with seed credentials |

Leave this terminal running while you use the frontend.

---

## 7. Background worker (Dramatiq) — when and why

### Why a separate worker?

| Mode | `JOB_BACKEND` | Behaviour |
|------|---------------|-----------|
| **Inline** (default) | `inline` | Fetch / score / image jobs run **inside** the API process. Simple for local demo. Heavy jobs can block API requests. |
| **Dramatiq** | `dramatiq` | API only **enqueues** jobs to Redis. A **separate worker process** executes them. Needed for production / long news ingest / parallel scoring. |

The worker must be a **second process** because:

1. Long-running ingest/scoring must not freeze HTTP.
2. You can restart or scale workers without restarting the API.
3. Dramatiq consumes from Redis — the API does not process those queues by itself.

### When you need the worker

Set in `.env`:

```env
JOB_BACKEND=dramatiq
REDIS_URL=redis://localhost:6379/0
```

Then in a **second terminal**:

```bash
cd ai-content-platform-backend
source .venv/bin/activate
bash scripts/run_worker.sh
```

Equivalent:

```bash
JOB_BACKEND=dramatiq REDIS_URL=redis://localhost:6379/0 \
  dramatiq app.workers --processes 1 --threads 1
```

| Command | What it does |
|---------|----------------|
| `bash scripts/run_worker.sh` | Starts Dramatiq consumers (`dramatiq app.workers`) |
| `--processes 1 --threads 1` | One worker process, one thread (stable for async DB sessions) |

**Important:** Entrypoint is `dramatiq app.workers` — **not** `app.modules.jobs`.

If `JOB_BACKEND=dramatiq` but **no worker** is running, Source “Run” jobs will stay queued and never finish.

If `JOB_BACKEND=inline`, **do not** need the worker.

---

## 8. Typical local terminal layout

```text
Terminal 1  →  Redis          (brew services start redis)
Terminal 2  →  API            (uvicorn app.main:app --reload --port 8000)
Terminal 3  →  Worker         (only if JOB_BACKEND=dramatiq)
Terminal 4  →  Frontend       (see ai-content-platform-frontend/README.md)
```

---

## 9. Verification checklist

After setup, confirm:

- [ ] `redis-cli ping` → `PONG` (if using Redis / Dramatiq)
- [ ] `psql "$DATABASE_URL_SYNC_OR_LOCAL" -c '\l'` shows `ai_content_platform` (or use your local `psql` / GUI)
- [ ] `alembic upgrade head` completed without errors
- [ ] `python scripts/seed_database.py` created admin user
- [ ] http://127.0.0.1:8000/api/v1/health returns OK
- [ ] http://127.0.0.1:8000/docs loads
- [ ] Login works with `admin@guardiq.com` / `Admin123!`
- [ ] Frontend `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1` and CORS includes frontend origin
- [ ] If `JOB_BACKEND=dramatiq`: worker log shows Dramatiq started; Sources → Run completes a job

---

## 10. Command cheat sheet

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
| `bash scripts/run_worker.sh` | Start background workers |
| `redis-cli ping` | Check Redis |
| `pytest` | Run tests (if configured) |

---

## 11. Project structure (short)

```text
app/
  api/             HTTP routes, schemas, middleware
  core/            Settings, JWT, logging, constants
  modules/         Domain modules (news, content, intelligence, …)
  infrastructure/  Postgres, Redis, LLM/image adapters, connectors
  workers/         Dramatiq actors (background jobs)
  main.py          API entrypoint
configs/           YAML prompts, brand, workflows, providers
scripts/           seed, worker, setup helpers
alembic/           Migrations
tests/             Unit / integration tests
```

---

## 12. API surface (starter)

All JSON under `/api/v1/` (see `/docs` for full list).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/v1/health` | No | Liveness |
| POST | `/api/v1/auth/login` | No | Email / password → tokens |
| POST | `/api/v1/auth/refresh` | No | Refresh access token |
| GET | `/api/v1/auth/me` | Yes | Current user |
| GET | `/api/v1/articles` | Yes | News feed |
| GET | `/api/v1/sources` | Yes | News sources |
| GET | `/api/v1/drafts` | Yes | Draft list |

Envelope shape: `{ "data": ..., "error": ..., "meta": { "request_id": "..." } }`

---

## 13. Production notes (short)

1. Set `APP_ENV=production`, `APP_DEBUG=false`, strong JWT secrets.
2. Prefer `JOB_BACKEND=dramatiq` + Redis + systemd (or similar) for API **and** worker.
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
| Jobs stuck in “queued” | Set `JOB_BACKEND=inline` **or** start `bash scripts/run_worker.sh` |
| CORS errors in browser | Add exact frontend origin to `CORS_ORIGINS` |
| AI provider is not configured | Set a supported `DEFAULT_LLM_PROVIDER` / `IMAGE_PROVIDER` and matching credentials |
| Worker crashes on import | Activate `.venv`; run from repo root; use `dramatiq app.workers` |
