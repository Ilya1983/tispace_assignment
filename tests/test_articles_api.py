import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import SAMPLE_ARTICLE_ID

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# GET /articles
# ---------------------------------------------------------------------------

async def test_list_articles_empty(client):
    resp = await client.get("/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["results"] == []


async def test_list_articles_with_data(client, sample_article):
    resp = await client.get("/articles")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["results"][0]["title"] == "Test Article Title"


async def test_list_articles_pagination(client, sample_article, sample_article_no_content):
    resp = await client.get("/articles?page=1&page_size=1")
    data = resp.json()
    assert data["total"] == 2
    assert len(data["results"]) == 1
    assert data["page"] == 1
    assert data["page_size"] == 1


async def test_list_articles_filter_by_source(client, sample_article):
    resp = await client.get("/articles?source=example.com")
    assert resp.json()["total"] == 1

    resp = await client.get("/articles?source=nonexistent.com")
    assert resp.json()["total"] == 0


async def test_list_articles_filter_by_keyword(client, sample_article):
    resp = await client.get("/articles?search_keyword=markets")
    assert resp.json()["total"] == 1

    resp = await client.get("/articles?search_keyword=crypto")
    assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# GET /articles/{id}
# ---------------------------------------------------------------------------

async def test_get_article_detail(client, sample_article):
    resp = await client.get(f"/articles/{SAMPLE_ARTICLE_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Test Article Title"
    assert "Full article content" in data["content"]


async def test_get_article_not_found(client):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/articles/{fake_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /articles/{id}/summary
# ---------------------------------------------------------------------------

async def test_get_summary_fresh(client, sample_article):
    resp = await client.get(f"/articles/{SAMPLE_ARTICLE_ID}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] == "This is a test summary."
    assert data["cached"] is False
    assert data["title"] == "Test Article Title"


async def test_get_summary_cached(client, sample_article, fake_redis):
    # First call — generates and caches
    resp1 = await client.get(f"/articles/{SAMPLE_ARTICLE_ID}/summary")
    assert resp1.status_code == 200
    assert resp1.json()["cached"] is False

    # Second call — served from cache
    resp2 = await client.get(f"/articles/{SAMPLE_ARTICLE_ID}/summary")
    assert resp2.status_code == 200
    assert resp2.json()["cached"] is True


async def test_get_summary_not_found(client):
    fake_id = uuid.uuid4()
    resp = await client.get(f"/articles/{fake_id}/summary")
    assert resp.status_code == 404


async def test_get_summary_no_content(client, sample_article_no_content):
    article_id = "11111111-2222-3333-4444-555555555555"
    resp = await client.get(f"/articles/{article_id}/summary")
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /articles/fetch
# ---------------------------------------------------------------------------

async def test_trigger_fetch(client):
    with patch(
        "app.routers.articles.fetch_and_store_articles",
        new_callable=AsyncMock,
    ) as mock_fetch:
        from app.schemas import FetchResult
        mock_fetch.return_value = FetchResult(fetched=3, skipped=1, failed=0)

        resp = await client.post("/articles/fetch?keyword=gold")
        assert resp.status_code == 200
        data = resp.json()
        assert data["fetched"] == 3
        assert data["skipped"] == 1
        assert data["failed"] == 0
