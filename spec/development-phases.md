# Development Phases

Each phase is a working increment. At the end of every phase you can run the app and verify something works before moving on.

---

## Phase 1 — Project Skeleton + Database

**Goal:** FastAPI app boots, connects to Postgres, Article model exists, tables created.

**What to build:**
- `requirements.txt` (all deps)
- `app/__init__.py`
- `app/config.py` (Settings class)
- `app/database.py` (async engine, session factory, `get_db` dependency)
- `app/models.py` (Article ORM model)
- `app/schemas.py` (all Pydantic schemas)
- `app/main.py` (FastAPI app with lifespan — DB connect/disconnect)
- `scripts/init_db.py`

**Verify:** Run `init_db.py` against a local Postgres. Confirm `articles` table exists. Start uvicorn, hit `GET /docs` — Swagger UI loads (no endpoints yet, that's fine).

**Dependencies:** Local Postgres running (or use Docker for just Postgres during dev).

---

## Phase 2 — CRUD Endpoints

**Goal:** All article endpoints work with manually inserted test data.

**What to build:**
- `app/routers/__init__.py`
- `app/routers/articles.py` — three GET endpoints:
  - `GET /articles` (paginated list)
  - `GET /articles/{id}` (detail)
  - `GET /articles/{id}/summary` (stub — returns 501 "not implemented yet")
- Register router in `main.py`

**Verify:** Insert a few rows into `articles` table manually (or via a quick script). Hit all endpoints via Swagger UI or curl. Confirm pagination works, 404s work, detail returns full content.

**Dependencies:** Phase 1.

---

## Phase 3 — Fetcher Service

**Goal:** Marketaux API + newspaper4k content scraping works, articles land in the DB.

**What to build:**
- `app/services/__init__.py`
- `app/services/fetcher.py`:
  - `fetch_from_marketaux(keyword)` — calls API, returns parsed list
  - `scrape_article_content(url)` — newspaper4k extraction
  - `fetch_and_store_articles(keyword, db_session)` — orchestrates both, dedup, insert
- `app/routers/articles.py` — add `POST /articles/fetch` endpoint
- `scripts/fetch.py` — standalone entry point (for cron later)

**Verify:** Hit `POST /articles/fetch?keyword=markets` via Swagger. Check DB — articles appear with content populated. Hit `GET /articles` — fetched articles show up. Run `scripts/fetch.py` from command line — same result.

**Dependencies:** Phase 2 + Marketaux API token.

---

## Phase 4 — LLM Summarizer + Redis Cache

**Goal:** Summary endpoint returns real LLM summaries, cached in Redis.

**What to build:**
- `app/redis.py` (client init/close, `get_redis` dependency)
- `app/services/cache.py` (`get_cached_summary`, `cache_summary`)
- `app/services/summarizer.py` (`summarize_article` — calls Claude Haiku 4.5)
- Update `app/main.py` — add Redis to lifespan (connect/disconnect)
- Update `app/routers/articles.py` — replace summary stub with real flow:
  check cache → miss → call summarizer → cache → return

**Verify:** Hit `GET /articles/{id}/summary` — first call takes 1-2 seconds (LLM call), returns summary. Hit it again — instant response (cache hit). Check Redis — key exists with TTL. Test with an article that has no content — returns 422.

**Dependencies:** Phase 3 + local Redis running + Anthropic API key.

---

## Phase 5 — Frontend

**Goal:** React demo UI showcases all endpoints.

**What to build:**
- `frontend/` — Vite + React project init
- `frontend/src/api.js` — fetch wrappers
- `frontend/src/pages/ArticleList.jsx`
- `frontend/src/pages/ArticleDetail.jsx` (with summary button)
- `frontend/src/pages/FetchTrigger.jsx`
- `frontend/src/App.jsx` + `main.jsx`
- Update `app/main.py` — add `StaticFiles` mount for `frontend/dist/`

**Verify:** `npm run build`, start FastAPI, open `http://localhost:8000/` in browser. Navigate through all pages. Click "Generate Summary" — see loading then result. Click again — instant. Trigger a fetch — see results.

**Dependencies:** Phase 4. Backend must be fully functional.

---

## Phase 6 — Tests

**Goal:** Test coverage for all backend logic. These tests are what a CI/CD pipeline runs before building the Docker image.

**What to build:**
- `tests/conftest.py` (fixtures: test DB, fakeredis, mocked HTTP)
- `tests/test_articles_api.py`
- `tests/test_fetcher.py`
- `tests/test_summarizer.py`
- `tests/test_cache.py`

**Verify:** `pytest` passes. All external calls (Marketaux, Claude, newspaper4k) are mocked. No real API keys needed to run tests.

**Dependencies:** Phase 5. Full backend must be stable.

---

## Phase 7 — Docker Container + Documentation

**Goal:** Single `docker build && docker run` gets everything working. README makes it reproducible.

**What to build:**
- `Dockerfile` (Python + Postgres + Redis + Node build + supervisord + cron)
- `supervisord.conf`
- `crontab`
- `scripts/entrypoint.sh`
- `.env.example`
- `README.md` (setup instructions, architecture overview, API examples, how to run)
- Example API responses in README or Postman collection

**CI/CD flow:** Tests run first. If they pass, Docker image gets built. The Dockerfile does not run tests — that's the pipeline's job.

**Verify:** `docker build -t data-summarization-service .` then `docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... -e MARKETAUX_API_TOKEN=... data-summarization-service`. Open browser, everything works. Wait for cron to fire (or set short interval), check logs — fetcher ran. Full end-to-end. README is followable by someone who's never seen the project.

**Dependencies:** Phase 6. Tests pass before you containerize.

---

## Phase Summary

| Phase | What you get at the end | Estimated session |
|-------|------------------------|-------------------|
| 1 | App boots, DB connected, table exists | ~1h |
| 2 | CRUD endpoints work with test data | ~1h |
| 3 | Fetcher fills DB from Marketaux + scraped content | ~1.5h |
| 4 | LLM summaries + Redis caching working | ~1h |
| 5 | React UI demonstrates all endpoints | ~2h |
| 6 | Tests pass, all external calls mocked | ~2h |
| 7 | Docker container runs everything + README | ~2h |

Total: ~10-11 hours across 7 sessions.

CI/CD order: Phase 6 (tests) gates Phase 7 (build). Tests fail → no image.

Each phase has a clear "done" state you can verify before context-switching.