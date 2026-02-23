import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import String, event
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Article


# ---------------------------------------------------------------------------
# Async SQLite engine — replaces Postgres for tests
# ---------------------------------------------------------------------------
# The Article model uses postgresql.UUID which SQLite doesn't support.
# We compile it as CHAR(32) so UUIDs round-trip correctly.

TEST_DATABASE_URL = "sqlite+aiosqlite://"


@pytest_asyncio.fixture
async def db_engine():
    from sqlalchemy.ext.compiler import compiles

    # Tell SQLAlchemy to render PostgreSQL UUID as CHAR(32) on SQLite
    @compiles(PG_UUID, "sqlite")
    def compile_pg_uuid_for_sqlite(type_, compiler, **kw):
        return "CHAR(32)"

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# Fake Redis
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def fake_redis():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.flushall()
    await r.aclose()


# ---------------------------------------------------------------------------
# Sample article fixture
# ---------------------------------------------------------------------------

SAMPLE_ARTICLE_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest_asyncio.fixture
async def sample_article(db_session):
    article = Article(
        id=SAMPLE_ARTICLE_ID,
        external_uuid="ext-uuid-001",
        title="Test Article Title",
        description="A short description",
        snippet="A snippet of the article...",
        content="Full article content for testing. " * 20,
        url="https://example.com/article-1",
        image_url="https://example.com/image.jpg",
        source="example.com",
        language="en",
        published_at=datetime(2026, 2, 20, 12, 0, 0, tzinfo=timezone.utc),
        search_keyword="markets",
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


@pytest_asyncio.fixture
async def sample_article_no_content(db_session):
    article = Article(
        id=uuid.UUID("11111111-2222-3333-4444-555555555555"),
        external_uuid="ext-uuid-002",
        title="Article Without Content",
        description="Scraping failed for this one",
        snippet="A snippet...",
        content=None,
        url="https://example.com/article-2",
        source="example.com",
        language="en",
        published_at=datetime(2026, 2, 19, 12, 0, 0, tzinfo=timezone.utc),
        search_keyword="markets",
    )
    db_session.add(article)
    await db_session.commit()
    await db_session.refresh(article)
    return article


# ---------------------------------------------------------------------------
# FastAPI test client with dependency overrides
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(db_session, fake_redis):
    from app.database import get_db
    from app.main import app
    from app.redis import get_redis

    async def override_get_db():
        yield db_session

    async def override_get_redis():
        return fake_redis

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = override_get_redis

    # Patch summarizer to avoid real API calls during endpoint tests
    with patch("app.routers.articles.summarize_article", new_callable=AsyncMock) as mock_summarize:
        mock_summarize.return_value = "This is a test summary."
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            ac._mock_summarize = mock_summarize  # expose for assertions
            yield ac

    app.dependency_overrides.clear()
