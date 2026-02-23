import redis.asyncio as redis

from app.config import settings

redis_client: redis.Redis | None = None


async def init_redis():
    global redis_client
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def get_redis() -> redis.Redis:
    return redis_client
