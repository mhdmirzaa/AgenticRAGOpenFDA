"""
Tests for the query/retrieval cache with Redis backend + graceful fallback.
[production item 7]
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.retrieval.cache as cache


@pytest.fixture(autouse=True)
def fresh_cache():
    os.environ.pop("REDIS_URL", None)
    from app.config import get_settings
    get_settings.cache_clear()
    cache.reset_backend()
    cache.clear_cache()
    yield
    cache.reset_backend()
    get_settings_cache_clear = get_settings
    get_settings_cache_clear.cache_clear()


class TestBackendSelection:
    def test_defaults_to_memory(self):
        assert cache.cache_backend_name() == "memory"

    def test_bad_redis_url_falls_back_to_memory(self):
        os.environ["REDIS_URL"] = "redis://127.0.0.1:6399/0"  # nothing listening
        from app.config import get_settings
        get_settings.cache_clear()
        cache.reset_backend()
        # unreachable Redis must NOT raise — degrade to memory
        assert cache.cache_backend_name() == "memory"


class TestRetrievalCache:
    def test_repeat_query_hits_cache_and_skips_compute(self):
        calls = {"n": 0}

        async def compute():
            calls["n"] += 1
            return [{"chunk_id": "a", "text": "t"}]

        async def run():
            r1 = await cache.cached_retrieval("Ibuprofen  WARNINGS", "dense", compute)
            r2 = await cache.cached_retrieval("ibuprofen warnings", "dense", compute)  # normalized-equal
            return r1, r2

        r1, r2 = asyncio.run(run())
        assert r1 == r2
        assert calls["n"] == 1  # second call served from cache
        stats = cache.cache_stats()
        assert stats["hits"] >= 1

    def test_mode_is_part_of_key(self):
        async def compute_dense():
            return [{"m": "dense"}]

        async def compute_hybrid():
            return [{"m": "hybrid"}]

        async def run():
            a = await cache.cached_retrieval("q", "dense", compute_dense)
            b = await cache.cached_retrieval("q", "hybrid", compute_hybrid)
            return a, b

        a, b = asyncio.run(run())
        assert a != b  # different modes -> different cache entries


class TestEmbedCache:
    def test_cached_embed_memoizes(self, monkeypatch):
        calls = {"n": 0}

        class FakeProvider:
            async def embed(self, text):
                calls["n"] += 1
                return [0.1, 0.2, 0.3]

        monkeypatch.setattr(cache, "get_provider", lambda: FakeProvider())

        async def run():
            await cache.cached_embed("What are ibuprofen warnings?")
            await cache.cached_embed("what are ibuprofen warnings?")  # normalized-equal

        asyncio.run(run())
        assert calls["n"] == 1
