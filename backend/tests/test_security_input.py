"""
Input validation, body-size limits, and SQL-injection safety (item 3).

Proves the attack is blocked: an oversized question is 422, an oversized body is
413, and a SQL-injection payload is stored/handled as inert DATA (parameterized
SQLAlchemy), never executed.
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


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="maistorage_in_")
    prev = {k: os.environ.get(k) for k in
            ("CHROMA_PATH", "LLM_PROVIDER", "MAX_QUESTION_CHARS",
             "MAX_BODY_BYTES", "DATABASE_URL")}
    os.environ.update({
        "CHROMA_PATH": tmp, "LLM_PROVIDER": "local",
        "MAX_QUESTION_CHARS": "200", "MAX_BODY_BYTES": "2000",
        "DATABASE_URL": f"sqlite:///{tmp}/in.db",
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


def test_empty_question_rejected(client):
    assert client.post("/ask-agentic", json={"question": "   "}).status_code == 422


def test_oversized_question_rejected(client):
    big = "a" * 500  # > MAX_QUESTION_CHARS=200
    assert client.post("/ask-agentic", json={"question": big}).status_code == 422
    assert client.post("/chat", json={"question": big}).status_code == 422


def test_oversized_body_rejected_413(client):
    # A body larger than MAX_BODY_BYTES=2000 is refused before handling.
    huge = {"question": "x" * 5000}
    assert client.post("/ask-agentic", json=huge).status_code == 413


def test_sql_injection_payload_is_stored_as_data():
    """A classic SQLi string round-trips verbatim and never executes."""
    tmp = tempfile.mkdtemp(prefix="maistorage_sqli_")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp}/sqli.db"
    _clear()
    from app.db import reset_engine, init_db, create_session, add_message, get_messages
    from sqlalchemy import inspect
    reset_engine()
    init_db()

    payload = "Robert'); DROP TABLE messages;-- and 1=1 UNION SELECT * FROM sessions"
    sid = create_session(owner="anon")
    add_message(sid, "user", payload)

    # The messages table still exists (the DROP was NOT executed)...
    from app.db import get_engine
    assert "messages" in inspect(get_engine()).get_table_names()
    # ...and the payload was stored verbatim as data.
    msgs = get_messages(sid)
    assert any(m["content"] == payload for m in msgs)

    os.environ.pop("DATABASE_URL", None)
    reset_engine()
    _clear()
