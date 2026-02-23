from uuid import UUID

import redis.asyncio as redis

from app.config import settings


async def get_cached_summary(article_id: UUID, r: redis.Redis) -> str | None:
    return await r.get(f"summary:{article_id}")


async def cache_summary(article_id: UUID, summary_text: str, r: redis.Redis) -> None:
    await r.set(f"summary:{article_id}", summary_text, ex=settings.summary_cache_ttl)
