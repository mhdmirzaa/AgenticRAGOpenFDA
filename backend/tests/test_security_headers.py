"""
Security response headers (security-hardening item 4).

Every API response carries anti-sniffing / anti-clickjacking / referrer / CSP
headers; HSTS appears only when enabled (prod TLS profile).
"""

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


def _make_client(**env):
    from fastapi.testclient import TestClient
    tmp = tempfile.mkdtemp(prefix="maistorage_hdr_")
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/h.db"
    os.environ.update(env)
    _clear()
    from app.providers import base as provider_base
    from app.db import reset_engine
    reset_engine()
    provider_base._provider_instance = FakeProvider()
    from app.main import app
    return TestClient(app)


def test_security_headers_present():
    with _make_client() as c:
        r = c.get("/health")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer"
        assert "default-src 'none'" in r.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
        # HSTS is off unless explicitly enabled (plain-HTTP dev).
        assert "strict-transport-security" not in r.headers
    os.environ.pop("DATABASE_URL", None)
    _clear()


def test_hsts_when_enabled():
    with _make_client(HSTS_ENABLED="1") as c:
        r = c.get("/health")
        assert "max-age=" in r.headers.get("strict-transport-security", "")
    os.environ.pop("HSTS_ENABLED", None)
    os.environ.pop("DATABASE_URL", None)
    _clear()
