"""
Final-answer cache (v3.2 performance). Exact-repeat, stateless questions return
the whole answer instantly instead of re-running generation.

Unit tests exercise the cache module directly; one integration test drives the
real /ask-agentic path twice and proves the second turn is served from cache.
"""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture(autouse=True)
def _fresh_cache():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.retrieval import cache as c
    c.reset_backend()
    c.clear_cache()
    c.clear_answer_cache_stats()
    yield
    c.reset_backend()
    c.clear_cache()
    c.clear_answer_cache_stats()
    get_settings.cache_clear()


# ------------------------------------------------------------------- unit
def test_store_then_get_roundtrip():
    from app.retrieval import cache as c
    payload = {"answer": "hi [1]", "citations": [], "refused": False, "blocked": False}
    assert c.get_cached_answer("What is X?", "baseline") is None      # miss
    c.store_cached_answer("What is X?", "baseline", payload)
    assert c.get_cached_answer("What is X?", "baseline") == payload    # hit
    stats = c.answer_cache_stats()
    assert stats["hits"] == 1 and stats["misses"] == 1


def test_normalized_key_hits_across_whitespace_and_case():
    from app.retrieval import cache as c
    c.store_cached_answer("What  is X?", "baseline", {"answer": "a"})
    assert c.get_cached_answer("  what is x? ", "baseline") == {"answer": "a"}


def test_mode_and_kind_are_isolated():
    from app.retrieval import cache as c
    c.store_cached_answer("q", "baseline", {"answer": "b"}, kind="ans")
    assert c.get_cached_answer("q", "optimized", kind="ans") is None   # mode differs
    assert c.get_cached_answer("q", "baseline", kind="sse") is None    # kind differs


def test_disabled_flag_never_caches():
    os.environ["ENABLE_ANSWER_CACHE"] = "0"
    from app.config import get_settings
    get_settings.cache_clear()
    from app.retrieval import cache as c
    try:
        c.store_cached_answer("q", "baseline", {"answer": "b"})
        assert c.get_cached_answer("q", "baseline") is None
    finally:
        os.environ.pop("ENABLE_ANSWER_CACHE", None)
        get_settings.cache_clear()


def test_sse_event_list_roundtrips():
    from app.retrieval import cache as c
    events = [{"type": "stage", "stage": "safety"}, {"type": "token", "text": "hi "},
              {"type": "done", "citations": [], "refused": False}]
    c.store_cached_answer("q", "optimized", events, kind="sse")
    assert c.get_cached_answer("q", "optimized", kind="sse") == events


# ------------------------------------------------------- integration (/ask)
@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from tests.test_e2e import FakeProvider

    tmp = tempfile.mkdtemp(prefix="maistorage_anscache_")
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"

    from app.config import get_settings
    get_settings.cache_clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod
    from app.retrieval.opensearch_store import reset_opensearch_store
    vs_mod.reset_vectorstore()
    reset_opensearch_store()
    provider_base._provider_instance = FakeProvider()

    from app.main import app
    with TestClient(app) as c:
        c.post("/ingest")
        yield c

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    get_settings.cache_clear()


def test_ask_agentic_second_call_is_served_from_cache(client):
    from app.retrieval import cache as c
    c.clear_answer_cache_stats()
    q = {"question": "How many annual leave days do full-time staff get?"}

    r1 = client.post("/ask-agentic", json=q)
    r2 = client.post("/ask-agentic", json=q)
    assert r1.status_code == r2.status_code == 200
    assert r1.json() == r2.json()                    # identical payload
    assert c.answer_cache_stats()["hits"] >= 1       # the repeat hit the cache
