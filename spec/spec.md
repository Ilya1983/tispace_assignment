# Data Summarization Service — Technical Spec

## Overview

A single-container backend service running FastAPI, PostgreSQL, Redis, and a scheduled fetcher under supervisord. Fetches financial news articles from Marketaux API, enriches them with full article content via web scraping, stores them in PostgreSQL, and provides endpoints for querying and summarizing articles using an LLM (on-demand, with Redis caching).

---

## Data Source

**Primary API:** [Marketaux](https://www.marketaux.com/) — `/v1/news/all`

**Free tier constraints:**
- 100 requests/day
- 3 articles per request (max ~300 articles/day)
- No `content` field — only `title`, `description`, `snippet` (truncated)
- `entities`, `keywords`, `relevance_score` — all empty on free tier

**Content enrichment:** Since the free tier provides no article body, each article's `url` is fetched and parsed using `newspaper4k` to extract full article text. This `content` field is what the LLM summarizes.

### Marketaux Free Tier Response Structure (actual)

```json
{
  "meta": { "found": 5258920, "returned": 3, "limit": 3, "page": 1 },
  "data": [
    {
      "uuid": "81e3694f-7870-4ecb-9b3e-d64d5e032b17",
      "title": "Gold climbs to 3-week high as US tariff ruling stokes uncertainty",
      "description": "Spot gold climbed 1.1% to $5,161.64 per ounce...",
      "keywords": "",
      "snippet": "Image credit: Getty Images\nGold prices climbed to a more than three-week high on Monday as...",
      "url": "https://gulfbusiness.com/gold-climbs-3-week-high-as-us-tariff-ruling/",
      "image_url": "https://gulfbusiness.com/wp-content/uploads/2025/10/Untitled-design-9.jpg",
      "language": "en",
      "published_at": "2026-02-23T07:25:23.000000Z",
      "source": "gulfbusiness.com",
      "relevance_score": null,
      "entities": [],
      "similar": []
    }
  ]
}
```

**Usable fields:** `uuid`, `title`, `description`, `snippet`, `url`, `image_url`, `language`, `published_at`, `source`
**Always empty/null on free tier:** `keywords`, `relevance_score`, `entities`, `similar`

---

## Database Schema

**Database:** PostgreSQL

### `articles` table

| Column           | Type         | Source              | Notes                              |
|------------------|--------------|---------------------|------------------------------------|
| `id`             | UUID (PK)    | Generated           | Internal primary key               |
| `external_uuid`  | VARCHAR      | Marketaux `uuid`    | UNIQUE constraint                  |
| `title`          | TEXT         | Marketaux           |                                    |
| `description`    | TEXT         | Marketaux           | 1-2 sentence summary from API     |
| `snippet`        | TEXT         | Marketaux           | Truncated preview (~150 chars)     |
| `content`        | TEXT         | newspaper4k scrape  | Full article body; nullable if scrape fails |
| `url`            | VARCHAR      | Marketaux           | Original article URL               |
| `image_url`      | VARCHAR      | Marketaux           | Nullable                           |
| `source`         | VARCHAR      | Marketaux           | e.g. "gulfbusiness.com"            |
| `language`       | VARCHAR      | Marketaux           | Default "en"                       |
| `published_at`   | TIMESTAMPTZ  | Marketaux           |                                    |
| `search_keyword` | VARCHAR      | Own metadata        | Query keyword used to fetch        |
| `fetched_at`     | TIMESTAMPTZ  | Own metadata        | When the scheduler pulled it       |

13 meaningful columns (well above the 5-attribute minimum).

---

## API Endpoints

| Method | Endpoint                   | Description                                      |
|--------|----------------------------|--------------------------------------------------|
| GET    | `/articles`                | Paginated list of articles from DB               |
| GET    | `/articles/{id}`           | Single article detail by internal UUID           |
| GET    | `/articles/{id}/summary`   | LLM-generated summary of article content, cached |
| POST   | `/articles/fetch`          | Manually trigger a data fetch (for demos/testing)|

### `GET /articles`

**Query params:**
- `page` (int, default 1)
- `page_size` (int, default 20)
- `search_keyword` (string, optional — filter by fetch keyword)
- `source` (string, optional — filter by source domain)

**Pagination:** Offset-based. Response includes `total`, `page`, `page_size`, `results`.

### `GET /articles/{id}`

Returns full article detail including `content`.

**Error:** 404 if not found.

### `GET /articles/{id}/summary`

Returns LLM-generated summary of the article's `content` field.

**Caching:** Summary is cached in Redis. Subsequent requests return cached version.

**Errors:**
- 404 if article not found
- 422 if article has no `content` (scrape failed)

### `POST /articles/fetch`

Manually triggers the same logic the scheduler runs. Useful for testing and demos.

**Query params:**
- `keyword` (string, default "markets")

---

## LLM Integration

**Provider:** Anthropic Claude API — Haiku 4.5 (`claude-haiku-4-5-20251001`, $1/$5 per MTok input/output)

**Use case:** Summarize the `content` field of an article into a concise 2-3 sentence summary.

**Strategy: On-demand (lazy), not pre-generated.**

Summaries are generated only when `GET /articles/{id}/summary` is called, not at fetch time. Rationale:
- Doesn't burn API credits on articles nobody looks at
- Makes caching demonstrable to the evaluator (first call is slow, second is instant)
- If summaries were pre-generated and stored in the DB, the Redis cache layer would serve no purpose

**Flow:**
1. `GET /articles/{id}/summary` is called
2. Check Redis cache for existing summary → return if found
3. Fetch article from DB → fail if no `content`
4. Call Claude API with article content
5. Cache result in Redis (TTL: 24 hours)
6. Return summary

---

## Scheduler

**Mechanism:** Cron job inside the container, managed by supervisord.

**Schedule:** Every 6 hours (default). Configurable via `FETCH_INTERVAL_HOURS` env var.

**Implementation:** A standalone Python script (`fetcher.py`) that shares the same codebase/models as the API. Cron invokes it on schedule. The `POST /articles/fetch` endpoint calls the same underlying function for manual triggers.

**Demo/evaluation convenience:** Set `FETCH_INTERVAL_HOURS` to a short value (e.g., 1 minute) or use `POST /articles/fetch` to trigger immediately. The README should document both approaches.

**Fetch budget per run (free tier math):**
- 100 requests/day ÷ 4 runs/day = 25 requests per run
- 25 requests × 3 articles/request = 75 articles per run
- Deduplication via `external_uuid` prevents re-inserting existing articles

**Fetch pipeline per run:**
1. Call `https://api.marketaux.com/v1/news/all` with configured keyword and `language=en`
2. For each article in response:
   - Skip if `external_uuid` already exists in DB (dedup)
   - Use `newspaper4k` to fetch and parse full article text from `url`
   - Insert into PostgreSQL with all metadata + extracted content
3. Log success/failure counts

**Error handling:** If `newspaper4k` fails to extract content for a URL, store the article with `content = NULL`. The summary endpoint will return 422 for these articles.

---

## Caching

**Technology:** Redis

**What's cached:** LLM summaries only.

**What's NOT cached (and why):**
- Article list/detail endpoints — Postgres handles single-row and paginated lookups fine. Caching these adds key management complexity for zero visible benefit in a demo.
- Marketaux API responses — the fetcher runs infrequently and the data is immediately persisted to the DB.

Redis serves one clear purpose: avoid redundant LLM calls. The evaluator can see it working (first summary request is slow, second is instant).

**Key format:** `summary:{article_id}`

**TTL:** 24 hours (configurable via `SUMMARY_CACHE_TTL` env var).

---

## Tech Stack

| Component        | Technology                          |
|------------------|-------------------------------------|
| Framework        | FastAPI                             |
| Database         | PostgreSQL                          |
| ORM              | SQLAlchemy (async with asyncpg)     |
| Cache            | Redis (via redis-py / aioredis)     |
| Scheduler        | Cron (managed by supervisord)       |
| Process manager  | supervisord                         |
| Data API         | Marketaux `/v1/news/all`            |
| Content scraping | newspaper4k                         |
| LLM              | Anthropic Claude API (Haiku 4.5)    |
| Testing          | pytest + httpx (async test client)  |
| Frontend         | React (Vite), served as static files by FastAPI |
| Containerization | Docker (single container)           |

---

## Containerization (Docker)

### Single Container Architecture

All services run inside one container, managed by supervisord.

**Supervised processes:**

| Process    | Role                                | Command                          |
|------------|-------------------------------------|----------------------------------|
| `uvicorn`  | FastAPI web server                  | `uvicorn app.main:app --host 0.0.0.0 --port 8000` |
| `postgres` | PostgreSQL database                 | `postgres -D /var/lib/postgresql/data` |
| `redis`    | Redis cache                         | `redis-server`                   |
| `cron`     | Scheduled fetcher                   | `cron -f` (runs `fetcher.py` on schedule) |

**Exposed port:** 8000 (FastAPI only)

### Dockerfile notes

- Base image: `python:3.12-slim`
- Install system packages: `postgresql`, `redis-server`, `supervisor`, `cron`, `libxml2-dev`, `libxslt1-dev`, `nodejs`, `npm`
- Install Python deps via `requirements.txt`
- Build frontend: `cd frontend && npm install && npm run build`
- Copy `supervisord.conf` into container
- Copy crontab file (configurable interval, defaults to every 6 hours)
- Entrypoint: `scripts/entrypoint.sh`

### Entrypoint script (`scripts/entrypoint.sh`)

Runs before supervisord starts. Handles two things:
1. **Export runtime env vars for cron** — cron does not inherit environment from the parent process. The entrypoint dumps env vars to `/etc/environment` so the cron job can source them.
2. **Initialize the database** — runs `scripts/init_db.py` to create tables.

```bash
#!/bin/bash
# Make runtime env vars available to cron
env >> /etc/environment

# Initialize DB tables
python scripts/init_db.py

# Start all services
exec supervisord -c /etc/supervisor/supervisord.conf
```

### Crontab

The cron job sources `/etc/environment` before running the fetcher:

```
0 */6 * * * . /etc/environment; cd /app && python scripts/fetch.py >> /var/log/fetcher.log 2>&1
```

---

## Environment Variables

### Secrets (must be provided at runtime, never committed)

| Variable               | Description                          | Required |
|------------------------|--------------------------------------|----------|
| `ANTHROPIC_API_KEY`    | Claude API key                       | Yes — app fails fast if missing |
| `MARKETAUX_API_TOKEN`  | Marketaux API key                    | Yes — app fails fast if missing |

Passed via `docker run -e` or `--env-file .env`. The repo contains only `.env.example` with placeholders.

### Internal (hardcoded defaults in `config.py`, safe to commit)

| Variable       | Default                                                      | Notes                        |
|----------------|--------------------------------------------------------------|------------------------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/articles` | Always localhost in container |
| `REDIS_URL`    | `redis://localhost:6379/0`                                   | Always localhost in container |

### Tunable config (sensible defaults, overridable at runtime)

| Variable               | Default    | Notes                                     |
|------------------------|------------|-------------------------------------------|
| `FETCH_KEYWORD`        | `markets`  | Keyword used for Marketaux queries        |
| `FETCH_INTERVAL_HOURS` | `6`        | Cron schedule; set low for demos          |
| `SUMMARY_CACHE_TTL`    | `86400`    | Redis TTL in seconds (24h)                |

### Cron environment gotcha

Cron does not inherit environment variables from the parent process. The container entrypoint dumps runtime env to `/etc/environment` before supervisord starts:

```bash
env >> /etc/environment
```

The crontab sources this file before running the fetcher:

```
0 */6 * * * . /etc/environment; cd /app && python scripts/fetch.py >> /var/log/fetcher.log 2>&1
```

Without this, the cron-invoked fetcher would crash because it cannot find `ANTHROPIC_API_KEY` and `MARKETAUX_API_TOKEN`.

---

## Frontend (Demo UI)

**Purpose:** A minimal React app to visually showcase all API endpoints. Not a production frontend — just enough for the evaluator to see the service working without curl/Postman.

**Tech:** React (Vite), built to static files, served by FastAPI via `StaticFiles` mount.

**Pages/Views:**

| View | What it demonstrates |
|------|---------------------|
| **Article List** | `GET /articles` — paginated table/cards with title, source, date. Pagination controls. |
| **Article Detail** | `GET /articles/{id}` — full article view (title, content, metadata). Click-through from list. |
| **Summary** | `GET /articles/{id}/summary` — button on detail page. Shows loading state on first call, instant on second (demonstrates cache). |
| **Fetch Trigger** | `POST /articles/fetch` — button + keyword input. Shows fetch results (count of fetched/skipped/failed). |

**Build & Serving:**
- Frontend is built at Docker build time (`npm run build`)
- Output goes to `frontend/dist/`
- FastAPI serves it as static files at `/` via `app.mount("/", StaticFiles(directory="frontend/dist", html=True))`
- API endpoints remain at `/articles/...` (no path conflict — API routes are registered before the static mount)

**No separate web server or process needed.** FastAPI handles both the API and serving the static build. No nginx, no extra supervisord entry.

---

## Testing

**Framework:** pytest (not JUnit — the assignment spec erroneously references Java tooling)

**Coverage targets:**
- Unit tests for data fetching & parsing logic
- Unit tests for article CRUD operations
- Unit tests for summary endpoint (mocked LLM calls)
- Integration tests for API endpoints using httpx AsyncClient

---

## Deliverables

- [ ] Source code in GitHub repository
- [ ] README with project overview and setup instructions
- [ ] Dockerfile with supervisord setup (single container)
- [ ] React demo UI served at `/` (article list, detail, summary, fetch trigger)
- [ ] Example API responses (Postman collection or documented in README)
- [ ] Unit tests with pytest

---

## Assignment Ambiguities — Resolved

| Ambiguity | Resolution |
|-----------|------------|
| "FastAPI Rest Framework (DRF)" | DRF is Django. Assignment means plain FastAPI. |
| Dynamic `{dataType}` in URLs | Fixed to `/articles`. One data type, not generic. |
| "ChatGPT" | Any LLM. Using Anthropic Claude Haiku 4.5 — cheapest option, more than sufficient for summarization. |
| "JUnit" | Copy-paste from Java template. Using pytest. |
| "POST" mentioned but no POST endpoint | Added `POST /articles/fetch` for manual trigger. |
| "at least 5 core attributes" | 13 columns in schema. |
| No content on free Marketaux tier | Scrape full text via newspaper4k from article URL. |
| Pagination format unspecified | Offset-based with `page` and `page_size` params. |
| Auth not mentioned | Not implemented (not required). |
| Scheduler mechanism unspecified | Cron via supervisord (not in-process APScheduler). Avoids coupling scheduler to API lifecycle. |
| Container architecture unspecified | Single container with supervisord managing all processes (FastAPI, Postgres, Redis, cron). |
| When to call LLM | On-demand at summary endpoint, not at fetch time. Makes Redis caching demonstrable. |
| What to cache | Summaries only. Article list/detail don't benefit from caching at demo scale. |
| Fetch frequency for demo | 6h default, configurable via env var. `POST /articles/fetch` for immediate trigger. |