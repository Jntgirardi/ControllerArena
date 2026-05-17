from __future__ import annotations

import json
import logging

import redis
from redis.exceptions import RedisError


logger = logging.getLogger(__name__)


class RedisCache:
    """Small Redis-backed cache layer that fails quietly when Redis is down."""

    def __init__(self, url: str, ttl: int = 120):
        self.ttl = ttl
        self.client = redis.from_url(url, decode_responses=True)

    def get(self, key: str):
        """Return a cached value or None when it does not exist."""
        try:
            value = self.client.get(key)
            return json.loads(value) if value is not None else None
        except RedisError as exc:
            logger.warning("Redis.get failed for '%s': %s", key, exc)
            return None

    def set(self, key: str, value, ttl: int | None = None) -> bool:
        """Store a JSON-serialized value with a TTL."""
        try:
            serialized = json.dumps(value, default=str)
            self.client.setex(key, ttl if ttl is not None else self.ttl, serialized)
            return True
        except RedisError as exc:
            logger.warning("Redis.set failed for '%s': %s", key, exc)
            return False

    def delete(self, key: str) -> bool:
        """Remove a single cache key."""
        try:
            self.client.delete(key)
            return True
        except RedisError as exc:
            logger.warning("Redis.delete failed for '%s': %s", key, exc)
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Remove all keys matching a Redis scan pattern."""
        try:
            keys = list(self.client.scan_iter(pattern))
            if keys:
                self.client.delete(*keys)
            return len(keys)
        except RedisError as exc:
            logger.warning("Redis.delete_pattern failed for '%s': %s", pattern, exc)
            return 0

    def ping(self) -> bool:
        """Check whether Redis is reachable."""
        try:
            return bool(self.client.ping())
        except RedisError:
            return False


class NoCache:
    """Null cache implementation used when Redis is disabled or unavailable."""

    def get(self, key: str):
        return None

    def set(self, key: str, value, ttl: int | None = None) -> bool:
        return False

    def delete(self, key: str) -> bool:
        return False

    def delete_pattern(self, pattern: str) -> int:
        return 0

    def ping(self) -> bool:
        return False


def build_cache(url: str, ttl: int, enabled: bool) -> RedisCache | NoCache:
    """Build the configured cache without letting Redis availability break the app."""
    if not enabled:
        logger.info("Redis cache disabled by REDIS_ENABLED=false.")
        return NoCache()

    try:
        cache = RedisCache(url=url, ttl=ttl)
        if cache.ping():
            logger.info("Redis cache connected at '%s'.", url)
            return cache
        raise RedisError("ping returned False")
    except RedisError as exc:
        logger.warning(
            "Could not connect to Redis at '%s': %s. Continuing without cache.",
            url,
            exc,
        )
        return NoCache()
