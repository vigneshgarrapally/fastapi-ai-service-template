"""Redis cache client — session data, rate limits, short-term memory.

A thin wrapper rather than a bare ``redis.asyncio.Redis`` handle so callers
depend on this module's small interface, not the full redis-py API surface —
swapping the backing store later (e.g. a managed cache service) touches one file.
"""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as redis
import structlog

logger = structlog.get_logger(__name__)

_client: redis.Redis | None = None


class CacheClient:
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def get_json(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        return json.loads(raw) if raw is not None else None

    async def set_json(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        await self._client.set(key, json.dumps(value), ex=ttl_seconds)

    async def delete(self, key: str) -> None:
        await self._client.delete(key)

    async def incr(self, key: str, ttl_seconds: int | None = None) -> int:
        """Atomically increment a counter, setting its TTL on first creation.

        Useful for a simple fixed-window rate limiter: call this, compare the
        returned count against your limit.
        """
        count = await self._client.incr(key)
        if count == 1 and ttl_seconds is not None:
            await self._client.expire(key, ttl_seconds)
        return count


async def init_cache_client(url: str) -> None:
    """Create the Redis client. Called once at startup."""
    global _client
    _client = redis.from_url(url, decode_responses=True)
    await _client.ping()
    logger.info("cache.connected")


def get_cache_client() -> CacheClient:
    if _client is None:
        raise RuntimeError("Cache client not initialized — call init_cache_client() at startup")
    return CacheClient(_client)


async def close_cache_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("cache.disconnected")
