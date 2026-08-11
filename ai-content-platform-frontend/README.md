# AI Content Intelligence Platform — Frontend (Client Handoff)

This is the **product + setup handbook** for the React dashboard. After you receive this codebase, use this file as the main reference for:

- What the product does
- How to install and run the UI against **your** backend / database
- What every page and major button does
- How to configure **Brand** (kit + Markdown profile + 12-step Brand Intelligence wizard)

| Related docs | Path |
|--------------|------|
| Backend install, Postgres, Redis, worker, env vars | [`../ai-content-platform-backend/README.md`](../ai-content-platform-backend/README.md) |
| Every backend env field (required / optional) | [`../ai-content-platform-backend/.env.example`](../ai-content-platform-backend/.env.example) |
| Example business relevance rubric | [`../docs/client-profile.md`](../docs/client-profile.md) |

---

## 1. What you are taking over

### Product in one paragraph

An enterprise workspace that turns **industry news** and **your own stories** into **LinkedIn-ready posts and images**, scored against **your brand profile**. Editors approve in the app, then **copy / download and publish manually on LinkedIn**. There is **no LinkedIn auto-post API**.

### How the pieces fit (your infrastructure)

```text
Browser (this frontend)
    ↓  REST  VITE_API_BASE_URL → …/api/v1
Backend (FastAPI)
    ↓
Your PostgreSQL  ← users, brand, articles, drafts, jobs, media keys
Your Redis       ← optional (Dramatiq workers)
Local media dir  ← generated images
LLM / image APIs ← keys in backend .env only (never in frontend)
```

- **Frontend** = UI only. No DB connection, no LLM keys.
- **Backend `.env`** = database URL, Redis, JWT, OpenAI/Gemini/etc.
- **Seed / migrations** = run on the backend against **your** Postgres (see backend README).

Default seed login (change in production):

- Email: `admin@guardiq.com`
- Password: `Admin123!`

---

## 2. First-time order (do this once)

1. Backend up + `alembic upgrade head` + `python scripts/seed_database.py` (backend README).
2. Frontend `.env.local` → `VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1` (or your API).
3. Log in at http://localhost:3000
4. **Brand** → fill kit + paste Markdown profile → **Save Brand**
5. Optional but recommended: **Brand → Start 12-step wizard** (LinkedIn + website + assets)
6. **Sources → Run all**
7. **News → Rescore** → mark Yes/No → **Draft**
8. **Drafts** → edit → **Approve** → **Generate image** → copy/download → post on LinkedIn yourself

---

## 3. Sidebar map

| Section | Item | Route |
|---------|------|--------|
| Main | Dashboard | `/app` |
| Create | News | `/app/news` |
| Create | Capture | `/app/capture` |
| Create | Plan | `/app/plan` |
| Create | Drafts | `/app/drafts` |
| Setup | Sources | `/app/sources` |
| Setup | Brand | `/app/brand` |
| More | Learning | `/app/learning` |
| More | Prompts | `/app/prompts` |
| More | Jobs | `/app/jobs` |
| More | Analytics | `/app/analytics` |
| More | Providers | `/app/providers` |
| More | Settings | `/app/settings` |
| More | Users | `/app/users` |

Also: `/app/brand/onboarding` (12-step wizard), `/app/brand/intelligence` (BI dashboard), `/app/drafts/:id` (editor).

Header extras: theme toggle, command palette / search, onboarding tour (also under Settings).

---

## 4. Page-by-page — what you can do

### 4.1 Login — `/login`

- Sign in with email + password (JWT session; frontend stores tokens and refreshes them).
- After seed: `admin@guardiq.com` / `Admin123!`.

---

### 4.2 Dashboard — `/app`

**Purpose:** At-a-glance health of the content pipeline.

**Typical UI**
- Pipeline rail: News → Draft → Visuals
- KPI cards: drafts generated today, approval queue, article count, running jobs, estimated cost, failures
- 7-day drafts chart
- Shortcuts under **What can I do?** (open Sources, News, Plan, Drafts, Analytics)
- Link toward **Publishing Plan / fortnight mix** when available

**When to use:** Morning check; after Runs/scoring to see jobs and queue size.

---

### 4.3 News — `/app/news`

**Purpose:** Browse ingested stories, see **relevance / sentiment / trends**, teach the brand with thumbs, and start educational drafts.

#### Top actions

| Control | What it does |
|---------|----------------|
| **Rescore** | Queues AI relevance scoring for new/unscored articles (uses Brand profile) |
| **Refresh** | Reloads the feed from the API |
| **How relevance works** (expand) | Short explanation of scoring |

#### Filters & sort

| Control | What it does |
|---------|----------------|
| **All / Relevant / Not relevant / Unscored** | Filter by AI + admin override status |
| **Newest / Relevance / Trending** | Sort order |
| **Search** | Title / source / summary / category |
| **Topic / category** | Narrow by category |
| **Trending now** chips | Topics with momentum; click to filter, click again to clear |
| **Previous / Next** | Pagination |

#### Per story row

| Control | What it does |
|---------|----------------|
| Status chip | Relevant / Not relevant / Scoring… / New |
| Fit label | Strong fit / Borderline / Weak fit (from AI 1–5 score) |
| Sentiment | Risk / urgency / regulatory-style label when present |
| External link | Open original article |
| **Yes** (thumbs up) | Mark relevant → updates Learning + brand preferences |
| **No** (thumbs down) | Mark not relevant → same learning path |
| **Draft** | Create educational LinkedIn draft → opens Draft detail (warns if story was “not relevant”) |

**Tips**
- Empty list → **Sources → Run all**, then wait / check **Jobs**, then Refresh.
- Scoring quality = quality of **Brand profile**.
- Prefer drafting from **Relevant** stories.

---

### 4.4 Capture — `/app/capture`

**Purpose:** Create **Success** or **Personal** posts from *your* story (not from news).

#### Wizard steps

| Step | What you do |
|------|-------------|
| **1. Type** | Choose Success story / Personal achievement (/ Educational if offered) |
| **2. Story** | Title + body; optional **voice record** (Azure Speech when backend `STT_PROVIDER=azure`) |
| **3. Questions** | Optional clarifying questions to improve the draft |
| **4. Photos** | None / upload / camera / planned shot list |
| **5. Generate** | **Write LinkedIn draft** → opens Draft detail |

**Tips**
- Plan page can deep-link here with `?content_type=success_story` or `personal_achievement`.
- Voice languages: backend Azure Speech + optional Translator.

---

### 4.5 Plan (Content Intelligence) — `/app/plan`

**Purpose:** AI-assisted **publishing mix** for the week/fortnight: opportunities, calendar, review queue.

#### Main actions

| Control | What it does |
|---------|----------------|
| **Regenerate plan** | Rebuild AI plan from brand mix + opportunities |
| **Seed calendar** | Place plan posts onto the calendar |
| **Capture success / personal** | Jump to Capture to fill mix gaps |
| Mix progress bars | Educational / Success / Personal vs Brand targets |
| **News opportunities** | Generate LinkedIn post / Save / Ignore per opportunity |
| **LinkedIn-ready posts** | **Approve** / **Reject** / **Regenerate** drafts from the plan |
| Strategist Copilot | Recommend / regenerate guidance (when shown) |
| Calendar | Assign / view scheduled slots |

**Tips**
- Mix targets come from **Brand → Publishing window & targets**.
- One-off News drafts still live under **Drafts**; Plan focuses on mix/calendar posts.

---

### 4.6 Drafts list — `/app/drafts`

**Purpose:** All drafts by status and content type.

| Control | What it does |
|---------|----------------|
| **New from News** | Jump to News |
| Status filters | All · Needs review · Approved · Rejected |
| Type filters | All · Educational · Success · Personal |
| Row click / **Open** | Draft detail |
| Quick **Approve** | Approve without opening (when shown) |

`/app/review` redirects here with Needs review.

---

### 4.7 Draft detail — `/app/drafts/:id`

**Purpose:** Finish the post: edit copy, approve, generate image, optional overlay/carousel.

#### Header / left (copy)

| Control | What it does |
|---------|----------------|
| **All drafts** | Back to list |
| **Copy post** | Clipboard — paste into LinkedIn manually |
| **Hear** / Stop | TTS read-aloud (Azure when configured) |
| Edit fields | Hook, body, CTA (and title when present) |
| LinkedIn preview | Fold-style preview |
| Source article | Expand link/summary when draft came from News |
| **Rewrite** panel | Scope: Whole post / Hook / Body / CTA + note → Regenerate |
| **Approve post** | Marks approved; learning can store example |
| **Reject** | Optional reason → Learning rules |

#### Right (visuals)

| Control | What it does |
|---------|----------------|
| Image count (1–4) | How many variants to generate |
| Guidance tip | Extra instruction for the image model |
| **Generate / Regenerate image** | Starts image job (may take ~30–70s+) |
| Gallery | Browse / download generated assets |
| **Text overlay (+ logo)** | Typography compositing with Brand fonts/colours/logo |
| **Multi-slide carousel** | Optional carousel export path |

**Recommended order:** Polish copy → **Approve** → **Generate image** → optional overlay → download → publish on LinkedIn yourself.

**Notes**
- Images use Brand Kit colours; readable headlines should use **typography overlay** (avoids AI misspellings in pixels).
- Storage: backend `STORAGE_PROVIDER=s3` or local — see backend README.

---

### 4.8 Sources — `/app/sources`

**Purpose:** News connectors that fill the News feed.

| Control | What it does |
|---------|----------------|
| **Run all** | Fetch every enabled source |
| **Run** (per row) | Fetch one source |
| **Configure** | Edit connector settings |
| Search / filters | Find sources; enabled vs all |
| Health / last fetch | Operational status |

#### Configure dialog (typical fields)

- **Name**
- **RSS:** feed URL, max items
- **NewsData (API):** query, language, country, categories, max items, paid plan flag
- **Schedule cron** (e.g. every few hours) — auto-fetch needs backend/worker alive
- **Enabled** on/off

**Tips**
- Empty catalog → backend `python scripts/seed_database.py`
- After Run → **Jobs** if stuck; then **News → Refresh**
- Manual **Run** always works even if cron is not firing

---

### 4.9 Brand — `/app/brand` (critical)

**Purpose:** Define the business. This drives **News relevance**, **draft voice**, **Plan mix**, and **image colours**.

#### Header buttons on Brand

| Button / link | What it does |
|---------------|----------------|
| **Complete Brand Intelligence** / **Start 12-step wizard** | Opens `/app/brand/onboarding` |
| **Sync Latest** | Re-fetch LinkedIn/website into Brand Memory (needs prior wizard + LinkedIn session) |
| **Re-analyze** | Re-run Brand Intelligence analysis |
| **Intelligence dashboard** | Opens `/app/brand/intelligence` |

#### Section 1 — Basics

| Field | Purpose |
|-------|---------|
| Organization name | Display / overlays |
| Tagline / services | Positioning line (e.g. IT Support \| Cyber \| Compliance) |
| Industry | Combobox or custom |
| Tone of voice | How posts should sound |
| Target audience | Who the post is for |

#### Section 2 — Look & visuals

| Field | Purpose |
|-------|---------|
| Primary / secondary / accent colours | Image palette + typography |
| Logo upload / replace | Used on text overlays (needs BI profile for some uploads) |
| Default image count | Variants per generate (e.g. 1–4) |
| Auto-generate image with draft | When on, image job may start after draft creation |

#### Section 3 — Publishing cadence

| Field | Purpose |
|-------|---------|
| Window: **weekly** or **fortnight** | Plan horizon |
| Targets: Educational / Success / Personal | Numbers Plan tries to hit |

#### Section 4 — Brand profile (Markdown) — most important for scoring

This Markdown is the **relevance + generation memory** (who you serve, what’s in/out of scope, UK focus, frameworks, exclusions).

**How to create it**

1. Click **Copy Claude / GPT prompt** (or **Show prompt**).
2. Paste into ChatGPT or Claude.
3. Answer with real business detail (sectors, services, exclusions, geography, buyer, voice).
4. Copy the model’s Markdown reply.
5. Click **Paste profile** → paste → **Use this profile**.
6. Review in Edit or Reading view.
7. Click **Save Brand**.

**What good profiles include**
- Business description & positioning (security-led MSP, etc.)
- Primary / secondary audiences (e.g. care, legal, accountancy)
- In-scope topics (Cyber Essentials, DSPT, MFA, M365, …)
- Explicit **exclusions** (out-of-scope sectors / topics)
- Geography (e.g. UK / North West & Central London)
- Tone rules and “never say” style guidance

**After Save**
- News scoring uses this profile.
- Draft generation uses it for angle and voice.
- News **Yes/No** further teaches preferences (see Learning).

Scraped hub (when BI has data): founder, company, LinkedIn link, topics, imported source snippets.

---

### 4.10 Brand Intelligence — 12-step wizard — `/app/brand/onboarding`

**Purpose:** Import LinkedIn, website, and assets into **Brand Memory**, review detections, then **Analyze** so the system learns writing DNA, visual DNA, and recommendations.

Progress shows **Step X of 12**. Use **Back** / **Continue** (or step-specific actions).

| # | Step | What you do | Why it matters |
|---|------|-------------|----------------|
| 1 | **Profile** | Use existing BI profile **or** create new (**Corporate** / **Personal** / **Product**), name it, optionally set **default** | Memory is per profile |
| 2 | **LinkedIn** | Paste LinkedIn URL. Prefer connected session (admin runs `scripts/linkedin_session_login.py` once). Advanced: paste About / posts manually | Voice, topics, post quality, images |
| 3 | **Website** | Website URL + **max pages to crawl** (1–40) | Messaging, services, claims |
| 4 | **Logo** | Upload variants: **primary / light / dark / icon** | Overlays & visual DNA |
| 5 | **Guidelines** | Upload brand guidelines (PDF/docs) | Formal brand rules |
| 6 | **Images** | Upload reference creatives | Visual style learning |
| 7 | **Videos** | Optional video references | Motion / style cues |
| 8 | **Documents** | Brochures, one-pagers, etc. | Claims & messaging |
| 9 | **Emails** | Sample emails (optional) | Written voice |
| 10 | **Review** | Inspect detections; edit tone; **Approve** or **Reject** review | Human gate before analysis finalises |
| 11 | **Analyze** | Starts job; watch pipeline stages until complete | Builds Brand Memory scores |
| 12 | **Dashboard** | Done → open Intelligence dashboard | See scores & recommendations |

**LinkedIn session (one-time, server/dev)**
1. On the machine that can open a browser: run backend `scripts/linkedin_session_login.py`, log in once.
2. Save `storage_state` via Brand Intelligence session API (admin).
3. Return to wizard with **URL only** → Continue → Analyze.

**Minimum useful wizard:** Profile + LinkedIn URL (+ session) + Website + primary logo → Review → Analyze.

---

### 4.11 Brand Intelligence dashboard — `/app/brand/intelligence`

**Purpose:** Scores and insights after Analyze.

**You typically see**
- Overall / health-style scores
- Writing DNA (tone, topics)
- Visual DNA / missing assets
- Audience hints
- Recommendations (prioritised)
- Sample quality posts from imports
- Actions: **Refresh**, **Re-analyze**, links back to Brand kit / Plan / wizard

Empty until onboarding Analyze has finished at least once.

---

### 4.12 Learning — `/app/learning`

**Purpose:** Durable feedback the models reuse.

| Tab | Meaning | How it gets filled |
|-----|---------|---------------------|
| **Examples** | Good writing samples | Approving strong drafts |
| **Rules** | Do / don’t instructions | Reject reasons; edits |
| **Preferences** | Soft preferences (incl. relevance) | News Yes/No; style prefs |

You can **Edit** / **Save** examples and rules where the UI allows. Prefer teaching via real Approve/Reject/thumbs rather than inventing rules blindly.

---

### 4.13 Prompts — `/app/prompts`

Read-only catalog of versioned prompts from backend `configs/prompts`. Expand to inspect. Normal operators do not edit here — engineers change YAML on the backend and redeploy.

---

### 4.14 Jobs — `/app/jobs`

Live table of background work: news ingest, rescoring, image generation, brand analyze, etc.

Check **status**, **type**, **errors**, **cost**, **provider**.  
If jobs stay **queued** forever with `JOB_BACKEND=dramatiq`, start `bash scripts/run_worker.sh` on the backend.

---

### 4.15 Analytics — `/app/analytics`

Cost, LLM call volume, model usage, provider health charts/tables. Populates after real scoring/generation traffic.

---

### 4.16 Providers — `/app/providers`

Which AI providers the backend sees as configured/healthy.  
**Keys are only in backend `.env`** — this page does not store secrets.

---

### 4.17 Settings — `/app/settings`

- Account / organisation display
- Theme: Light / Dark / System (browser-local)
- **Replay onboarding tour**
- Shortcuts to Brand, Brand Intelligence, Sources, Providers, Users, Capture

---

### 4.18 Users — `/app/users`

Read-only member list (name, email, role) with search/filter. Invites/role changes depend on your backend admin process.

---

## 5. Day-to-day operating loop

```text
Morning
  Sources → Run all (or rely on cron + worker)
  News → Rescore → Yes/No on borderline items

Create educational
  News → Draft → edit → Approve → Generate image → Copy/Download → LinkedIn (manual)

Create success / personal
  Capture wizard → Approve → image → LinkedIn (manual)

Plan the period
  Brand targets already set → Plan → Regenerate → Seed calendar → Approve mix posts

Improve quality
  Learning from approvals/rejections
  Occasional Brand Sync Latest / Re-analyze
```

---

## 6. Install & run (this repo)

### Prerequisites

| Need | Notes |
|------|--------|
| Node.js **20+** | `node -v` / `npm -v` |
| Backend API | Your Postgres + env configured (backend README) |
| Browser | Chrome / Edge / Firefox / Safari |

### Install

```bash
cd ai-content-platform-frontend
npm install
cp .env.example .env.local
```

### `.env.local`

```env
# Must include /api/v1 — point at YOUR backend
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

| Variable | Required? | Notes |
|----------|-----------|--------|
| `VITE_API_BASE_URL` | Yes (for non-default hosts) | Public at build time — **no secrets** |

Backend `CORS_ORIGINS` must include the exact UI origin (e.g. `http://localhost:3000`).

### Dev server

```bash
npm run dev
```

Open **http://localhost:3000** (port in `vite.config.ts`).

### Production build

```bash
npm run build      # output: dist/
npm run preview    # optional smoke test
npm run lint
```

Build-time env example:

```env
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
```

### Typical three terminals

```text
1  Backend API     uvicorn app.main:app --reload --port 8000
2  Worker          bash scripts/run_worker.sh   # if JOB_BACKEND=dramatiq
3  Frontend        npm run dev
```

---

## 7. Verification checklist (handoff acceptance)

- [ ] Login works against **your** API / DB
- [ ] Brand saved (colours + Markdown profile)
- [ ] Optional: 12-step wizard Analyze completed; Intelligence dashboard shows scores
- [ ] Sources Run all succeeds; News shows articles
- [ ] Rescore + Yes/No works
- [ ] Draft from News opens editor; Approve works
- [ ] Image generate completes; file downloadable; object saved under backend local media dir
- [ ] Capture produces a success/personal draft
- [ ] Plan regenerate respects Brand mix targets
- [ ] Jobs/Analytics show activity
- [ ] No CORS / 401 loops in browser console

---

## 8. Troubleshooting

| Symptom | Likely fix |
|---------|------------|
| Blank page / can’t login | Backend down; wrong `VITE_API_BASE_URL`; CORS |
| Empty News | Seed DB; Run Sources; check Jobs / worker |
| Everything “not relevant” | Improve Brand Markdown; Rescore; use Yes/No |
| Drafts weak / off-voice | Tone, audience, profile Markdown; Learning examples |
| Image dull / wrong colours | Save Brand colours; regenerate; use typography for text |
| Image job fails | Backend `IMAGE_PROVIDER` + keys; Jobs error message; check local media dir permissions |
| Jobs stuck queued | `JOB_BACKEND=inline` **or** start Dramatiq worker + Redis |
| Sync Latest fails | Finish wizard + LinkedIn session first |
| Hear / voice capture fails | Backend Azure Speech / Translator env |
| 401 after deploy | New JWT secrets → users must log in again |

---

## 9. Glossary

| Term | Meaning |
|------|---------|
| **Brand Kit** | Colours, logo, tone, audience, cadence on `/app/brand` |
| **Brand profile (Markdown)** | Long-form scoring/generation memory |
| **Brand Intelligence (BI)** | Wizard + memory + DNA + dashboard |
| **Relevance** | 1–5 fit of a news story to your profile |
| **Sentiment** | Security-news style axes (risk, urgency, …) |
| **Trends** | Topic momentum across recent ingest |
| **Educational draft** | Usually from News |
| **Success / Personal** | Usually from Capture |
| **Plan** | Mix + calendar for the publishing window |
| **Learning** | Examples / rules / preferences from human feedback |
| **Worker** | Separate process that runs queued backend jobs |

---

## 10. Stack & source layout

React 19 · Vite · TypeScript · Tailwind CSS v4 · Radix · TanStack Query/Table · Recharts · Motion · sonner · driver.js

| Path | Role |
|------|------|
| `src/pages/` | Screens |
| `src/api/` | REST client + Brand Intelligence API |
| `src/components/` | Product UI |
| `src/design-system/` | Primitives |
| `src/layouts/` | Sidebar shell |
| `src/lib/routes.ts` | Route constants |

---

## Constitution

Frontend-only package. Do not put secrets here. Do not call LLM/image vendors from the browser. All durable data lives in **your** backend database and local media storage.
