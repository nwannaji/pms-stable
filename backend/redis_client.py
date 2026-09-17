"""Redis cache client with in-memory fallback."""

import os
import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class InMemoryCache:
    """Simple in-memory cache that mimics the Redis interface used by the app."""

    def __init__(self):
        self._store: dict = {}

    def get(self, key: str):
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry["expires_at"] and datetime.now(timezone.utc) > entry["expires_at"]:
            del self._store[key]
            return None
        return entry["value"]

    def set(self, key: str, value, ttl: int = None):
        """Set a cache value with an optional TTL in seconds."""
        expires_at = None
        if ttl:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        self._store[key] = {"value": value, "expires_at": expires_at}

    def delete(self, key: str):
        self._store.pop(key, None)

    def exists(self, key: str) -> bool:
        return self.get(key) is not None

    def keys(self, pattern: str = "*") -> list:
        # Simple pattern matching — only supports trailing wildcard
        if pattern == "*":
            return list(self._store.keys())
        if pattern.endswith("*"):
            prefix = pattern.rstrip("*")
            return [k for k in self._store if k.startswith(prefix)]
        return [k for k in self._store if k == pattern]


class RedisCache:
    """Redis-backed cache using the `redis` package."""

    def __init__(self, url: str):
        import redis
        self._client = redis.from_url(url, decode_responses=True)

    def get(self, key: str):
        value = self._client.get(key)
        if value is None:
            return None
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    def set(self, key: str, value, ttl: int = None):
        serialized = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            self._client.setex(key, ttl, serialized)
        else:
            self._client.set(key, serialized)

    def delete(self, key: str):
        self._client.delete(key)

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(key))

    def keys(self, pattern: str = "*") -> list:
        return [k for k in self._client.scan_iter(match=pattern)]


def _init_cache():
    """Try to connect to Redis; fall back to in-memory cache if unavailable."""
    try:
        import redis
        client = redis.from_url(REDIS_URL, decode_responses=True)
        client.ping()
        logger.info("Connected to Redis at %s", REDIS_URL)
        return RedisCache(REDIS_URL)
    except Exception as exc:
        logger.warning("Redis unavailable (%s) — using in-memory cache", exc)
        return InMemoryCache()


cache = _init_cache()