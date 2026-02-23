from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx
from sqlalchemy import select

from app.models import Article
from app.services.fetcher import (
    MARKETAUX_URL,
    fetch_and_store_articles,
    fetch_from_marketaux,
    scrape_article_content,
)


# ---------------------------------------------------------------------------
# fetch_from_marketaux
# ---------------------------------------------------------------------------

MARKETAUX_RESPONSE = {
    "meta": {"found": 100, "returned": 2, "limit": 3, "page": 1},
    "data": [
        {
            "uuid": "uuid-001",
            "title": "Article One",
            "description": "Desc one",
            "snippet": "Snippet one",
            "url": "https://example.com/one",
            "image_url": "https://example.com/one.jpg",
            "source": "example.com",
            "language": "en",
            "published_at": "2026-02-20T12:00:00.000000Z",
        },
        {
            "uuid": "uuid-002",
            "title": "Article Two",
            "description": "Desc two",
            "snippet": "Snippet two",
            "url": "https://example.com/two",
            "image_url": None,
            "source": "other.com",
            "language": "en",
            "published_at": "2026-02-21T08:00:00.000000Z",
        },
    ],
}


@pytest.mark.asyncio
@respx.mock
async def test_fetch_from_marketaux_parses_response():
    respx.get(MARKETAUX_URL).mock(return_value=httpx.Response(200, json=MARKETAUX_RESPONSE))
    articles = await fetch_from_marketaux("markets")
    assert len(articles) == 2
    assert articles[0]["uuid"] == "uuid-001"
    assert articles[1]["title"] == "Article Two"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_from_marketaux_empty_data():
    respx.get(MARKETAUX_URL).mock(
        return_value=httpx.Response(200, json={"meta": {}, "data": []})
    )
    articles = await fetch_from_marketaux("nothing")
    assert articles == []


@pytest.mark.asyncio
@respx.mock
async def test_fetch_from_marketaux_http_error():
    respx.get(MARKETAUX_URL).mock(return_value=httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_from_marketaux("error")


# ---------------------------------------------------------------------------
# scrape_article_content
# ---------------------------------------------------------------------------

@patch("app.services.fetcher.newspaper.article")
def test_scrape_article_content_success(mock_article):
    mock_result = MagicMock()
    mock_result.text = "Full article text here."
    mock_article.return_value = mock_result

    result = scrape_article_content("https://example.com/article")
    assert result == "Full article text here."
    mock_article.assert_called_once_with("https://example.com/article")


@patch("app.services.fetcher.newspaper.article")
def test_scrape_article_content_returns_none_on_failure(mock_article):
    mock_article.side_effect = Exception("Connection timeout")

    result = scrape_article_content("https://bad-url.com")
    assert result is None


@patch("app.services.fetcher.newspaper.article")
def test_scrape_article_content_returns_none_on_empty_text(mock_article):
    mock_result = MagicMock()
    mock_result.text = ""
    mock_article.return_value = mock_result

    result = scrape_article_content("https://example.com/empty")
    assert result is None


# ---------------------------------------------------------------------------
# fetch_and_store_articles
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@respx.mock
@patch("app.services.fetcher.scrape_article_content", return_value="Scraped content.")
async def test_fetch_and_store_articles(mock_scrape, db_session):
    respx.get(MARKETAUX_URL).mock(return_value=httpx.Response(200, json=MARKETAUX_RESPONSE))

    result = await fetch_and_store_articles("markets", db_session)

    assert result.fetched == 2
    assert result.skipped == 0
    assert result.failed == 0

    rows = (await db_session.execute(select(Article))).scalars().all()
    assert len(rows) == 2
    assert rows[0].content == "Scraped content."


@pytest.mark.asyncio
@respx.mock
@patch("app.services.fetcher.scrape_article_content", return_value="Content.")
async def test_fetch_and_store_articles_dedup(mock_scrape, db_session):
    respx.get(MARKETAUX_URL).mock(return_value=httpx.Response(200, json=MARKETAUX_RESPONSE))

    # First fetch — stores 2 articles
    result1 = await fetch_and_store_articles("markets", db_session)
    assert result1.fetched == 2

    # Second fetch — same data, should skip all
    result2 = await fetch_and_store_articles("markets", db_session)
    assert result2.fetched == 0
    assert result2.skipped == 2


@pytest.mark.asyncio
@respx.mock
async def test_fetch_and_store_articles_missing_uuid(db_session):
    bad_data = {
        "data": [
            {"title": "No UUID Article", "url": "https://example.com/no-uuid"},
        ]
    }
    respx.get(MARKETAUX_URL).mock(return_value=httpx.Response(200, json=bad_data))

    result = await fetch_and_store_articles("markets", db_session)
    assert result.failed == 1
    assert result.fetched == 0
