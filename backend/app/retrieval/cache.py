"""
Query / retrieval cache (bonus, performance).  [M7; Redis-backed in item 7]

Caches:
  (a) query embeddings   keyed by (embed_model, normalized_question)
  (b) retrieval results  keyed by (mode, normalized_query)

Backend is Redis when REDIS_URL is set (shared + survives restarts); otherwise
an in-process LRU. A Redis failure degrades gracefully to memory so a cache
outage never breaks a request. Hit/miss stats + the active backend are surfaced
on /health.
"""

from __future__ import annotations

import json
import logging
from collections import OrderedDict

from app.config import get_settings
from app.providers.base import get_provider

logger = logging.getLogger(__name__)

_MAX_ENTRIES = 512
_stats = {"hits": 0, "misses": 0}


# ------------------------------------------------------------------ backends
class _MemoryBackend:
    name = "memory"

    def __init__(self) -> None:
        self._d: "OrderedDict[str, str]" = OrderedDict()

    def get(self, key: str) -> str | None:
        val = self._d.get(key)
        if val is not None:
            self._d.move_to_end(key)
        return val

    def set(self, key: str, value: str, ttl: int) -> None:
        self._d[key] = value
        self._d.move_to_end(key)
        if len(self._d) > _MAX_ENTRIES:
            self._d.popitem(last=False)

    def clear(self) -> None:
        self._d.clear()

    def size(self) -> int:
        return len(self._d)


class _RedisBackend:
    name = "redis"

    def __init__(self, client) -> None:
        self._r = client

    def get(self, key: str) -> str | None:
        return self._r.get(key)

    def set(self, key: str, value: str, ttl: int) -> None:
        self._r.set(key, value, ex=ttl if ttl > 0 else None)

    def clear(self) -> None:
        try:
            self._r.flushdb()
        except Exception:
            pass

    def size(self) -> int:
        try:
            return int(self._r.dbsize())
        except Exception:
            return -1


_backend = None


def get_backend():
    """Return the active cache backend, choosing Redis when reachable."""
    global _backend
    if _backend is not None:
        return _backend

    url = get_settings().redis_url
    if url:
        try:
            import redis  # lazy: optional dependency
            client = redis.Redis.from_url(url, decode_responses=True)
            client.ping()
            _backend = _RedisBackend(client)
            logger.info("cache backend: redis (%s)", url)
            return _backend
        except Exception as e:
            logger.warning("Redis unavailable (%s); falling back to memory cache", e)

    _backend = _MemoryBackend()
    return _backend


def reset_backend() -> None:
    """Drop the backend singleton (tests / config changes)."""
    global _backend
    _backend = None


def cache_backend_name() -> str:
    return get_backend().name


def cache_stats() -> dict:
    """Return hit/miss counters + backend info."""
    total = _stats["hits"] + _stats["misses"]
    ratio = _stats["hits"] / total if total else 0.0
    backend = get_backend()
    return {
        **_stats,
        "backend": backend.name,
        "size": backend.size(),
        "hit_ratio": round(ratio, 3),
    }


def clear_cache() -> None:
    """Empty the cache and reset counters (used by tests)."""
    get_backend().clear()
    _stats["hits"] = 0
    _stats["misses"] = 0


def _normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


# --------------------------------------------------------------- embeddings
async def cached_embed(text: str) -> list[float]:
    """Embed `text` via the configured provider, memoized by (model, question)."""
    settings = get_settings()
    key = f"emb:{settings.embed_model}:{_normalize(text)}"
    backend = get_backend()

    raw = backend.get(key)
    if raw is not None:
        _stats["hits"] += 1
        try:
            return json.loads(raw)
        except Exception:
            pass  # corrupt entry -> recompute

    _stats["misses"] += 1
    vector = await get_provider().embed(text)
    backend.set(key, json.dumps(vector), settings.cache_ttl_seconds)
    return vector


# ------------------------------------------------------ retrieval results
async def cached_retrieval(query: str, mode: str, compute):
    """Return cached retrieval candidates for (mode, query), else compute+store.

    `compute` is an async callable returning a JSON-serializable list of
    candidate dicts.
    """
    settings = get_settings()
    key = f"ret:{mode}:{_normalize(query)}"
    backend = get_backend()

    raw = backend.get(key)
    if raw is not None:
        _stats["hits"] += 1
        try:
            return json.loads(raw)
        except Exception:
            pass

    _stats["misses"] += 1
    candidates = await compute()
    try:
        backend.set(key, json.dumps(candidates), settings.cache_ttl_seconds)
    except Exception as e:
        logger.warning("retrieval cache store skipped: %s", e)
    return candidates
