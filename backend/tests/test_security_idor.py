"""
IDOR / access control on session_id + trace_id (security-hardening item 2).

Proves: ids are unguessable uuid4; a malformed/sequential id is rejected (404)
before any lookup; and with AUTH_ENABLED one caller cannot read another caller's
session or trace (404, not 403 — no enumeration leak).
"""

import os
import re
import sys
import tempfile
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e import FakeProvider

KEY_A = "key-alice-000"
KEY_B = "key-bob-111"


def _clear():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.security import reset_limiter
    reset_limiter()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="maistorage_idor_")
    prev = {k: os.environ.get(k) for k in
            ("CHROMA_PATH", "LLM_PROVIDER", "AUTH_ENABLED", "API_KEYS",
             "RATE_LIMIT_ENABLED", "DATABASE_URL")}
    os.environ.update({
        "CHROMA_PATH": tmp, "LLM_PROVIDER": "local",
        "AUTH_ENABLED": "1", "API_KEYS": f"{KEY_A},{KEY_B}",
        "RATE_LIMIT_ENABLED": "0", "DATABASE_URL": f"sqlite:///{tmp}/idor.db",
    })
    _clear()
    from app.providers import base as provider_base
    from app.db import reset_engine
    from app.retrieval.opensearch_store import reset_opensearch_store
    reset_engine()
    reset_opensearch_store()
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


def test_session_id_is_unguessable_uuid4():
    """The generated id is 128-bit random hex, never sequential."""
    from app.db import create_session
    import os as _os
    _os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mkdtemp() + "/g.db"
    _clear()
    from app.db import reset_engine, init_db
    reset_engine(); init_db()
    a = create_session(owner="anon")
    b = create_session(owner="anon")
    assert re.fullmatch(r"[0-9a-f]{32}", a)
    assert a != b
    # Not sequential: the ids share no long common prefix.
    assert a[:8] != b[:8]


def test_malformed_ids_are_404(client):
    # Sequential / non-uuid ids are rejected before any store lookup.
    for bad in ("1", "42", "abc", "../etc/passwd", "1' OR '1'='1"):
        assert client.get(f"/sessions/{bad}/messages",
                          headers={"X-API-Key": KEY_A}).status_code == 404
        assert client.get(f"/trace/{bad}",
                          headers={"X-API-Key": KEY_A}).status_code == 404


def test_caller_cannot_read_another_callers_session(client):
    # Alice creates a session and writes to it.
    sid = client.post("/sessions", headers={"X-API-Key": KEY_A}).json()["session_id"]
    client.post("/ask-agentic", json={"question": "hi", "session_id": sid},
                headers={"X-API-Key": KEY_A})

    # Alice can read her own session.
    own = client.get(f"/sessions/{sid}/messages", headers={"X-API-Key": KEY_A})
    assert own.status_code == 200

    # Bob (valid key, different caller) cannot — 404, not 403.
    other = client.get(f"/sessions/{sid}/messages", headers={"X-API-Key": KEY_B})
    assert other.status_code == 404


def test_caller_cannot_read_another_callers_trace(client):
    # Alice runs a turn and gets a trace_id.
    r = client.post("/ask-agentic", json={"question": "What are the warnings for ibuprofen?"},
                    headers={"X-API-Key": KEY_A})
    assert r.status_code == 200
    trace_id = r.json()["trace_id"]
    assert trace_id

    assert client.get(f"/trace/{trace_id}", headers={"X-API-Key": KEY_A}).status_code == 200
    # Bob cannot read Alice's trace.
    assert client.get(f"/trace/{trace_id}", headers={"X-API-Key": KEY_B}).status_code == 404
    # A guessed (well-formed but non-existent) id is also 404.
    assert client.get(f"/trace/{uuid.uuid4()}", headers={"X-API-Key": KEY_B}).status_code == 404
