import logging
from datetime import datetime

import httpx
import newspaper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Article
from app.schemas import FetchResult

logger = logging.getLogger(__name__)

MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"


async def fetch_from_marketaux(keyword: str) -> list[dict]:
    params = {
        "api_token": settings.marketaux_api_token,
        "search": keyword,
        "language": "en",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(MARKETAUX_URL, params=params, timeout=30)
        response.raise_for_status()
    return response.json().get("data", [])


def scrape_article_content(url: str) -> str | None:
    try:
        art = newspaper.article(url)
        return art.text if art.text else None
    except Exception as e:
        logger.warning("Failed to scrape %s: %s", url, e)
        return None


async def fetch_and_store_articles(keyword: str, db: AsyncSession) -> FetchResult:
    articles_data = await fetch_from_marketaux(keyword)

    fetched = 0
    skipped = 0
    failed = 0

    for item in articles_data:
        external_uuid = item.get("uuid")
        if not external_uuid:
            failed += 1
            continue

        exists = (
            await db.execute(
                select(Article.id).where(Article.external_uuid == external_uuid)
            )
        ).scalar_one_or_none()

        if exists:
            skipped += 1
            continue

        content = scrape_article_content(item.get("url", ""))

        published_at = None
        if item.get("published_at"):
            try:
                published_at = datetime.fromisoformat(
                    item["published_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        article = Article(
            external_uuid=external_uuid,
            title=item.get("title", ""),
            description=item.get("description"),
            snippet=item.get("snippet"),
            content=content,
            url=item.get("url", ""),
            image_url=item.get("image_url"),
            source=item.get("source"),
            language=item.get("language", "en"),
            published_at=published_at,
            search_keyword=keyword,
        )
        db.add(article)
        fetched += 1

    await db.commit()
    logger.info("Fetch complete: fetched=%d skipped=%d failed=%d", fetched, skipped, failed)
    return FetchResult(fetched=fetched, skipped=skipped, failed=failed)
