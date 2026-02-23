# Project Structure

```
data-summarization-service/
│
├── Dockerfile
├── supervisord.conf
├── crontab
├── requirements.txt
├── .env.example
├── README.md
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app, lifespan events, static file mount
│   ├── config.py               # Pydantic Settings — loads all env vars
│   ├── database.py             # SQLAlchemy async engine + session factory
│   ├── redis.py                # Redis client singleton
│   ├── models.py               # SQLAlchemy ORM model (Article)
│   ├── schemas.py              # Pydantic request/response schemas
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   └── articles.py         # All /articles endpoints
│   │
│   └── services/
│       ├── __init__.py
│       ├── fetcher.py          # Marketaux API calls + newspaper4k scraping
│       ├── summarizer.py       # Claude API integration
│       └── cache.py            # Redis get/set for summaries
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx             # Router + layout
│       ├── main.jsx            # Entry point
│       ├── api.js              # API client (fetch wrappers for all endpoints)
│       └── pages/
│           ├── ArticleList.jsx     # GET /articles — paginated list
│           ├── ArticleDetail.jsx   # GET /articles/{id} — full article + summary button
│           └── FetchTrigger.jsx    # POST /articles/fetch — manual trigger UI
│
├── scripts/
│   ├── entrypoint.sh           # Container entrypoint: env export, DB init, start supervisord
│   ├── fetch.py                # Cron entry point — imports and runs app.services.fetcher
│   └── init_db.py              # One-off: create tables if they don't exist
│
└── tests/
    ├── __init__.py
    ├── conftest.py             # Shared fixtures (test DB, mock Redis, mock HTTP)
    ├── test_articles_api.py    # Endpoint tests (GET /articles, GET /articles/{id})
    ├── test_fetcher.py         # Fetcher logic (Marketaux parsing, dedup, scraping)
    ├── test_summarizer.py      # Summarizer (mocked Claude calls, cache hit/miss)
    └── test_cache.py           # Redis cache operations
```

---

## File Responsibilities

### Root level

| File | Purpose |
|------|---------|
| `Dockerfile` | Single container: Python + Postgres + Redis + supervisor + cron |
| `supervisord.conf` | Manages 4 processes: uvicorn, postgres, redis, cron |
| `crontab` | Schedule for `scripts/fetch.py` (default every 6h) |
| `requirements.txt` | All Python dependencies |
| `.env.example` | Placeholder template for secrets only (`ANTHROPIC_API_KEY`, `MARKETAUX_API_TOKEN`) |
| `README.md` | Setup instructions, API docs, example responses |

### `app/main.py`

FastAPI application factory. Handles:
- App instantiation
- Lifespan events: connect to DB and Redis on startup, disconnect on shutdown
- Router registration (`app.include_router(articles.router)`)
- Static file mount for frontend (`app.mount("/", StaticFiles(...))` — registered last, after API routes)

No business logic here. Just wiring.

### `app/config.py`

Single `Settings` class using `pydantic-settings`. Three categories of env vars:

```python
class Settings(BaseSettings):
    # Internal — hardcoded defaults, always localhost inside the container
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/articles"
    redis_url: str = "redis://localhost:6379/0"

    # Secrets — no defaults, app fails fast if missing
    anthropic_api_key: str
    marketaux_api_token: str

    # Tunable — sensible defaults, overridable at runtime
    fetch_keyword: str = "markets"
    fetch_interval_hours: int = 6
    summary_cache_ttl: int = 86400
```

Imported as a singleton everywhere. No scattered `os.getenv()` calls.

Secrets are passed via `docker run -e` or `--env-file .env`. The repo only contains `.env.example` with placeholders.

### `app/database.py`

- Async SQLAlchemy engine (`create_async_engine`)
- `AsyncSession` factory
- `get_db()` dependency for FastAPI endpoints

### `app/redis.py`

- Redis client init/close
- `get_redis()` dependency for FastAPI endpoints

### `app/models.py`

Single SQLAlchemy model:

```python
class Article(Base):
    __tablename__ = "articles"

    id = Column(UUID, primary_key=True, default=uuid4)
    external_uuid = Column(String, unique=True, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    snippet = Column(Text)
    content = Column(Text, nullable=True)  # null if scrape failed
    url = Column(String, nullable=False)
    image_url = Column(String, nullable=True)
    source = Column(String)
    language = Column(String, default="en")
    published_at = Column(DateTime(timezone=True))
    search_keyword = Column(String)
    fetched_at = Column(DateTime(timezone=True), default=func.now())
```

### `app/schemas.py`

Pydantic models for API input/output:

- `ArticleListItem` — subset of fields for list endpoint (no `content`)
- `ArticleDetail` — full article including `content`
- `ArticleSummary` — `{ id, title, summary, cached }`
- `PaginatedResponse` — `{ total, page, page_size, results }`
- `FetchResult` — `{ fetched, skipped, failed }`

### `app/routers/articles.py`

All four endpoints:

| Endpoint | Handler | Dependencies |
|----------|---------|-------------|
| `GET /articles` | `list_articles()` | DB session |
| `GET /articles/{id}` | `get_article()` | DB session |
| `GET /articles/{id}/summary` | `get_summary()` | DB session, Redis, Summarizer |
| `POST /articles/fetch` | `trigger_fetch()` | DB session, Fetcher |

Thin handlers — they validate input, call services, return responses. No business logic in the router.

### `app/services/fetcher.py`

Two responsibilities:
1. **Call Marketaux API** — fetch articles by keyword, parse JSON response
2. **Scrape content** — for each article URL, use newspaper4k to extract full text

Exposed function: `fetch_and_store_articles(keyword, db_session)` → returns count of fetched/skipped/failed.

Used by both the cron script and the `POST /articles/fetch` endpoint.

### `app/services/summarizer.py`

Single responsibility: call Claude Haiku 4.5 with article content, return summary text.

Exposed function: `summarize_article(content: str) → str`

No caching logic here — that's in `cache.py`. This module only talks to the LLM API.

### `app/services/cache.py`

Redis operations for summaries:
- `get_cached_summary(article_id) → str | None`
- `cache_summary(article_id, summary_text, ttl)`

The summary endpoint in the router orchestrates: check cache → miss → call summarizer → store in cache → return.

### `frontend/`

Minimal React app (Vite) with three pages. Built to static files at Docker build time, served by FastAPI.

| File | Purpose |
|------|---------|
| `api.js` | Thin fetch wrappers for all four API endpoints. Single place to change base URL if needed. |
| `ArticleList.jsx` | Paginated list of articles. Each row links to detail. Pagination controls. Demonstrates `GET /articles`. |
| `ArticleDetail.jsx` | Full article view + "Generate Summary" button. Button shows loading spinner on first click, instant result on second. Demonstrates `GET /articles/{id}` and `GET /articles/{id}/summary` (and cache behavior). |
| `FetchTrigger.jsx` | Keyword input + "Fetch Now" button. Shows result count (fetched/skipped/failed). Demonstrates `POST /articles/fetch`. |

**No component library.** Plain CSS or minimal inline styles. The point is to demonstrate the API, not win a design award.

**Build output:** `frontend/dist/` — copied into the container image, served by FastAPI at `/`.

### `scripts/entrypoint.sh`

Container entrypoint. Runs before supervisord:

```bash
#!/bin/bash
# Dump runtime env vars to /etc/environment so cron can access them.
# Cron does NOT inherit env from the parent process — without this,
# the fetcher script would crash because it can't find API keys.
env >> /etc/environment

# Create DB tables
python scripts/init_db.py

# Start all services
exec supervisord -c /etc/supervisor/supervisord.conf
```

This is the Dockerfile's `ENTRYPOINT`. It bridges the gap between `docker run -e` env vars and cron's isolated environment.

### `scripts/fetch.py`

Standalone entry point for cron. Does:
1. Load config (env vars available via `/etc/environment`, sourced in crontab)
2. Create a DB session (sync or one-off async)
3. Call `fetch_and_store_articles()`
4. Log results
5. Exit

This is what cron executes. It imports from `app.services.fetcher` — same code path as the manual POST endpoint.

Crontab line:
```
0 */6 * * * . /etc/environment; cd /app && python scripts/fetch.py >> /var/log/fetcher.log 2>&1
```

### `scripts/init_db.py`

Run once by `entrypoint.sh` on container startup. Creates tables via `Base.metadata.create_all()`. No migrations framework (overkill for an assignment).

### `tests/`

| File | What it tests |
|------|--------------|
| `conftest.py` | Test DB (SQLite in-memory or test Postgres), mock Redis via `fakeredis`, mock HTTP via `respx` or `responses` |
| `test_articles_api.py` | All four endpoints via `httpx.AsyncClient` — status codes, pagination, 404s |
| `test_fetcher.py` | Marketaux response parsing, dedup logic, newspaper4k extraction (mocked HTTP) |
| `test_summarizer.py` | Claude API call (mocked), response parsing |
| `test_cache.py` | Redis get/set/miss behavior via `fakeredis` |

---

## Dependency Flow

```
Browser (frontend/dist/)
    └── FastAPI (serves static + API)

routers/articles.py
    ├── services/fetcher.py      (POST /articles/fetch)
    ├── services/summarizer.py   (GET /articles/{id}/summary)
    ├── services/cache.py        (GET /articles/{id}/summary)
    ├── models.py                (all endpoints)
    └── schemas.py               (all endpoints)

scripts/fetch.py
    └── services/fetcher.py

services/fetcher.py
    ├── Marketaux API (external HTTP)
    ├── newspaper4k (external HTTP)
    └── models.py (DB writes)

services/summarizer.py
    └── Anthropic API (external HTTP)

services/cache.py
    └── Redis

frontend/src/api.js
    └── FastAPI endpoints (same origin, no CORS needed)
```

No circular dependencies. Services don't import from routers. Routers don't import from each other.

---

## Environment Variables — Summary

### `.env.example` (committed to repo)

```
# Required — pass via docker run -e or --env-file
ANTHROPIC_API_KEY=your-key-here
MARKETAUX_API_TOKEN=your-token-here

# Optional overrides (defaults in app/config.py)
# FETCH_KEYWORD=markets
# FETCH_INTERVAL_HOURS=6
# SUMMARY_CACHE_TTL=86400
```

### Running the container

```bash
# With -e flags
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e MARKETAUX_API_TOKEN=e9NUYi... \
  data-summarization-service

# Or with env file
docker run -p 8000:8000 --env-file .env data-summarization-service
```

### Env flow through the container

```
docker run -e SECRETS=...
    └── entrypoint.sh
        ├── env >> /etc/environment    (makes secrets available to cron)
        ├── python scripts/init_db.py  (DB tables)
        └── supervisord
            ├── uvicorn    (reads env directly — inherits from parent)
            ├── postgres   (no env needed)
            ├── redis      (no env needed)
            └── cron
                └── fetch.py  (sources /etc/environment before running)
```