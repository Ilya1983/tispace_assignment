import uuid

import pytest

from app.services.cache import cache_summary, get_cached_summary

pytestmark = pytest.mark.asyncio


ARTICLE_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


async def test_get_cached_summary_miss(fake_redis):
    result = await get_cached_summary(ARTICLE_ID, fake_redis)
    assert result is None


async def test_cache_and_get_summary(fake_redis):
    await cache_summary(ARTICLE_ID, "A cached summary.", fake_redis)
    result = await get_cached_summary(ARTICLE_ID, fake_redis)
    assert result == "A cached summary."


async def test_cache_summary_sets_ttl(fake_redis):
    await cache_summary(ARTICLE_ID, "Summary with TTL.", fake_redis)
    ttl = await fake_redis.ttl(f"summary:{ARTICLE_ID}")
    assert ttl > 0


async def test_cache_key_format(fake_redis):
    await cache_summary(ARTICLE_ID, "Check key.", fake_redis)
    value = await fake_redis.get(f"summary:{ARTICLE_ID}")
    assert value == "Check key."
