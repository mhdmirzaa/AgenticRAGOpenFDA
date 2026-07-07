"""
Errors/logging, CORS allowlist, health minimalism, telegram auth (items 6-8).

Proves: every response carries a request id; /health leaks no internal error
strings; CORS echoes only allowlisted origins (never "*" / an arbitrary origin);
and the Telegram bot presents the backend API key when configured.
"""

import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e import FakeProvider


def _clear():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.security import reset_limiter
    reset_limiter()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    tmp = tempfile.mkdtemp(prefix="maistorage_hard_")
    prev = {k: os.environ.get(k) for k in ("CHROMA_PATH", "LLM_PROVIDER",
                                           "CORS_ORIGINS", "DATABASE_URL")}
    os.environ.update({
        "CHROMA_PATH": tmp, "LLM_PROVIDER": "local",
        "CORS_ORIGINS": "http://localhost:3000",
        "DATABASE_URL": f"sqlite:///{tmp}/h.db",
    })
    _clear()
    from app.providers import base as provider_base
    from app.db import reset_engine
    reset_engine()
    provider_base._provider_instance = FakeProvider()
    from app.main import app
    with TestClient(app) as c:
        yield c
    provider_base.reset_provider()
    reset_engine()
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _clear()


def test_request_id_on_every_response(client):
    assert client.get("/health").headers.get("x-request-id")


def test_health_has_no_internal_error_strings(client):
    body = client.get("/health").json()
    # Store status never carries a raw exception string.
    assert "error" not in body.get("store", {})
    assert "error" not in body.get("chroma", {})


def test_cors_allowlist_only(client):
    ok = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    evil = client.get("/health", headers={"Origin": "http://evil.example"})
    # An off-allowlist origin is never reflected, and never "*".
    assert evil.headers.get("access-control-allow-origin") not in (
        "*", "http://evil.example")


def test_telegram_presents_api_key_when_configured():
    os.environ["BACKEND_API_KEY"] = "secret-bot-key"
    captured: dict = {}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"answer": "ok", "citations": []}

    class _FakeClient:
        async def post(self, url, json=None, headers=None):
            captured["headers"] = headers or {}
            return _FakeResp()

    from app.services.telegram.handlers import answer_question
    try:
        asyncio.run(answer_question("hi", client=_FakeClient()))
        assert captured["headers"].get("X-API-Key") == "secret-bot-key"
    finally:
        os.environ.pop("BACKEND_API_KEY", None)


def test_telegram_omits_key_when_unset():
    os.environ.pop("BACKEND_API_KEY", None)
    captured: dict = {}

    class _FakeResp:
        def raise_for_status(self): pass
        def json(self): return {"answer": "ok", "citations": []}

    class _FakeClient:
        async def post(self, url, json=None, headers=None):
            captured["headers"] = headers or {}
            return _FakeResp()

    from app.services.telegram.handlers import answer_question
    asyncio.run(answer_question("hi", client=_FakeClient()))
    assert "X-API-Key" not in captured["headers"]
