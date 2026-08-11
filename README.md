# AI Content Intelligence Platform

Enterprise LinkedIn content intelligence platform (greenfield rewrite).

Editors discover industry news, score it against a client brand profile, generate LinkedIn drafts and images, review/approve, then **publish manually** (no LinkedIn auto-post API).

## Repositories

| Folder | Purpose | Setup guide |
|--------|---------|-------------|
| [`ai-content-platform-backend/`](ai-content-platform-backend/) | FastAPI API, workers, pipelines | **[Backend README](ai-content-platform-backend/README.md)** |
| [`ai-content-platform-frontend/`](ai-content-platform-frontend/) | React product dashboard | **[Frontend README](ai-content-platform-frontend/README.md)** (install + **page-by-page client guide**) |

Environment variable reference (every field, required vs optional):  
[`ai-content-platform-backend/.env.example`](ai-content-platform-backend/.env.example)

Architecture: [`ai-content-platform-backend/docs/architecture/SOFTWARE_ARCHITECTURE_v3.2.md`](ai-content-platform-backend/docs/architecture/SOFTWARE_ARCHITECTURE_v3.2.md)

Client relevance rubric: [`docs/client-profile.md`](docs/client-profile.md)

## Client handover package

| Document | Audience |
|----------|----------|
| [`docs/PROJECT_HANDOVER.md`](docs/PROJECT_HANDOVER.md) | Master handover (product + technical) |
| [`docs/FEATURE_MATRIX.md`](docs/FEATURE_MATRIX.md) | Implementation status matrix |
| [`docs/API_REFERENCE.md`](docs/API_REFERENCE.md) | FastAPI endpoint inventory (from routers) |
| [`docs/CLIENT_USER_GUIDE.md`](docs/CLIENT_USER_GUIDE.md) | Business-user how-to |
| [`docs/DEVELOPER_HANDOVER.md`](docs/DEVELOPER_HANDOVER.md) | Engineer onboarding |
| [`docs/DEPLOYMENT_RUNBOOK.md`](docs/DEPLOYMENT_RUNBOOK.md) | Deploy local → production |
| [`docs/TROUBLESHOOTING_RUNBOOK.md`](docs/TROUBLESHOOTING_RUNBOOK.md) | Diagnostics |

---

## What you need (local)

| Service | Required? | Why |
|---------|-----------|-----|
| Python 3.11+ | Yes | Backend |
| Node.js 20+ | Yes | Frontend |
| PostgreSQL | Yes | App database (`ai_content_platform`) |
| Redis | If using Dramatiq workers | Job broker (`JOB_BACKEND=dramatiq`) |
| Qdrant | Optional | Article embeddings |
| LLM / image API keys | Optional | Real AI (`mock` works without keys) |

Full install commands (Postgres local vs server, Redis, worker, checks): see the **Backend README**.

---

## Quick start (after reading the repo READMEs)

### Backend

```bash
cd ai-content-platform-backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit DATABASE_URL + JWT secrets
# Ensure Postgres (and Redis if needed) are running — see Backend README
alembic upgrade head
python scripts/seed_database.py
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Optional second terminal (only when `.env` has `JOB_BACKEND=dramatiq`):

```bash
bash scripts/run_worker.sh
```

Default login after seed: `admin@guardiq.com` / `Admin123!`

### Frontend

```bash
cd ai-content-platform-frontend
npm install
cp .env.example .env.local    # VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
npm run dev
```

Open **http://localhost:3000**

---

## Why the worker is separate

- `JOB_BACKEND=inline` — jobs run inside the API process (simple local demo; no worker).
- `JOB_BACKEND=dramatiq` — API only enqueues work to Redis; you must run `bash scripts/run_worker.sh` so ingest/scoring/images actually execute without blocking HTTP.

Details: [Backend README → Background worker](ai-content-platform-backend/README.md#7-background-worker-dramatiq--when-and-why).

---

## Delivery scope (product)

- News connectors (RSS / NCSC / MSRC / NewsData / others as configured)
- Relevance, sentiment, trends → scored feed
- Draft generation + review / learning loop
- Image pipeline behind a swappable provider (`mock` \| `openai` \| `comfyui`)
- Manual LinkedIn publish by the client
