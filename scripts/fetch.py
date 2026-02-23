"""Standalone fetcher entry point for cron."""

import asyncio

from app.config import settings
from app.database import async_session
from app.services.fetcher import fetch_and_store_articles


async def main():
    async with async_session() as db:
        result = await fetch_and_store_articles(settings.fetch_keyword, db)
    print(f"Fetch complete: fetched={result.fetched} skipped={result.skipped} failed={result.failed}")


if __name__ == "__main__":
    asyncio.run(main())
