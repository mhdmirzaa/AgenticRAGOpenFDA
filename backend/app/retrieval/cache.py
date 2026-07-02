"""
Embedding cache (bonus, FR-8 performance).  [M7].
A small in-process LRU cache for query embeddings so repeated / re-retried
queries in the agent loop don't pay the embed cost twice. Keyed by
(embed_model, text). Safe to clear; never persisted.
"""

from __future__ import annotations

from collections import OrderedDict

from app.config import get_settings
from app.providers.base import get_provider

_MAX_ENTRIES = 512
_cache: "OrderedDict[tuple[str, str], list[float]]" = OrderedDict()

# Simple counters for observability (surfaced in /health and eval logs).
_stats = {"hits": 0, "misses": 0}


def cache_stats() -> dict:
    """Return hit/miss counters."""
    total = _stats["hits"] + _stats["misses"]
    ratio = _stats["hits"] / total if total else 0.0
    return {**_stats, "size": len(_cache), "hit_ratio": round(ratio, 3)}


def clear_cache() -> None:
    """Empty the cache (used by tests)."""
    _cache.clear()
    _stats["hits"] = 0
    _stats["misses"] = 0


async def cached_embed(text: str) -> list[float]:
    """Embed `text` via the configured provider, memoized by (model, text)."""
    settings = get_settings()
    key = (settings.embed_model, text)

    cached = _cache.get(key)
    if cached is not None:
        _cache.move_to_end(key)
        _stats["hits"] += 1
        return cached

    _stats["misses"] += 1
    provider = get_provider()
    vector = await provider.embed(text)

    _cache[key] = vector
    _cache.move_to_end(key)
    if len(_cache) > _MAX_ENTRIES:
        _cache.popitem(last=False)
    return vector
