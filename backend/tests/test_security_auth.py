"""
Auth + rate limiting (security-hardening item 1).

Proves the attack is blocked: unauthenticated cost/mutating requests are 401,
a bad key is 401, an authenticated caller passes, over-limit is 429, and /health
stays public. Offline + deterministic (FakeProvider, temp store, no API key).
"""

import os
import sys
import tempfile
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e import FakeProvider

KEY = "test-key-abc123"


def _clear():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.security import reset_limiter
    reset_limiter()


@pytest.fixture()
def authed_client():
    """A TestClient with AUTH_ENABLED and one valid key. Env restored on teardown."""
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="maistorage_sec_")
    prev = {k: os.environ.get(k) for k in
            ("CHROMA_PATH", "LLM_PROVIDER", "AUTH_ENABLED", "API_KEYS",
             "RATE_LIMIT_ENABLED", "DATABASE_URL")}
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"
    os.environ["AUTH_ENABLED"] = "1"
    os.environ["API_KEYS"] = KEY
    os.environ["RATE_LIMIT_ENABLED"] = "0"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/sec.db"
    _clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod
    from app.retrieval.opensearch_store import reset_opensearch_store
    from app.db import reset_engine
    vs_mod.reset_vectorstore()
    reset_opensearch_store()
    reset_engine()
    provider_base._provider_instance = FakeProvider()

    from app.main import app
    with TestClient(app) as c:
        yield c

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    reset_engine()
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _clear()


def test_health_is_public(authed_client):
    r = authed_client.get("/health")
    assert r.status_code == 200


def test_unauthenticated_is_401(authed_client):
    assert authed_client.post("/sessions").status_code == 401
    assert authed_client.post("/ask-agentic", json={"question": "hi"}).status_code == 401
    assert authed_client.post("/ingest/fda", json={}).status_code == 401
    assert authed_client.get(f"/trace/{uuid.uuid4()}").status_code == 401
    # SSE endpoint is gated before streaming begins.
    assert authed_client.post("/chat", json={"question": "hi"}).status_code == 401


def test_bad_key_is_401(authed_client):
    r = authed_client.post("/sessions", headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_valid_key_passes(authed_client):
    r = authed_client.post("/sessions", headers={"X-API-Key": KEY})
    assert r.status_code == 200
    assert r.json()["session_id"]


def test_rate_limit_returns_429():
    """With rate limiting enabled and a tiny budget, over-limit yields 429."""
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="maistorage_rl_")
    prev = {k: os.environ.get(k) for k in
            ("CHROMA_PATH", "LLM_PROVIDER", "AUTH_ENABLED",
             "RATE_LIMIT_ENABLED", "RATE_LIMIT_DEFAULT_PER_MIN", "DATABASE_URL")}
    os.environ.update({
        "CHROMA_PATH": tmp, "LLM_PROVIDER": "local",
        "AUTH_ENABLED": "0", "RATE_LIMIT_ENABLED": "1",
        "RATE_LIMIT_DEFAULT_PER_MIN": "3",
        "DATABASE_URL": f"sqlite:///{tmp}/rl.db",
    })
    _clear()
    from app.providers import base as provider_base
    from app.db import reset_engine
    from app.retrieval.opensearch_store import reset_opensearch_store
    reset_engine()
    reset_opensearch_store()
    provider_base._provider_instance = FakeProvider()

    try:
        from app.main import app
        with TestClient(app) as c:
            codes = [c.post("/sessions").status_code for _ in range(6)]
        assert 429 in codes, codes
        # The first few succeed, then the limiter cuts in.
        assert codes[0] == 200
        assert codes.count(429) >= 1
    finally:
        provider_base.reset_provider()
        reset_engine()
        for k, v in prev.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        _clear()
