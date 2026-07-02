"""
HTTP tests for chat persistence + session endpoints.  [production item 2]

Drives the real FastAPI app with the deterministic FakeProvider and a temp
SQLite DB, verifying:
- POST /sessions creates a session
- POST /chat with a session_id persists the user + assistant messages
  (assistant carries citations + trace_id)
- GET /sessions/{id}/messages returns the conversation in order
- a follow-up turn accumulates history (memory) in the same session
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e import FakeProvider


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    tmp = tempfile.mkdtemp(prefix="maistorage_sess_")
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(tmp, 'sess.db')}"

    from app.config import get_settings
    get_settings.cache_clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod
    import app.db as db_mod

    vs_mod.reset_vectorstore()
    db_mod.reset_engine()
    provider_base._provider_instance = FakeProvider()

    from app.main import app
    with TestClient(app) as c:
        c.post("/ingest")  # build the index once
        yield c

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    db_mod.reset_engine()
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)


def _chat(client, question, session_id=None):
    payload = {"question": question, "optimized": False}
    if session_id:
        payload["session_id"] = session_id
    events = []
    with client.stream("POST", "/chat", json=payload) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line and line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def test_create_session(client):
    r = client.post("/sessions")
    assert r.status_code == 200
    sid = r.json()["session_id"]
    assert sid


def test_chat_persists_messages_with_session(client):
    sid = client.post("/sessions").json()["session_id"]
    _chat(client, "How many annual leave days do full-time staff get?", session_id=sid)

    r = client.get(f"/sessions/{sid}/messages")
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["trace_id"]  # assistant message carries the trace id


def test_followup_accumulates_history(client):
    sid = client.post("/sessions").json()["session_id"]
    _chat(client, "How many public holidays does MaiStorage observe annually?", session_id=sid)
    _chat(client, "What encryption does MaiVault use for data at rest?", session_id=sid)

    msgs = client.get(f"/sessions/{sid}/messages").json()["messages"]
    # two full turns => four messages, still in chronological order
    assert len(msgs) == 4
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]


def test_messages_for_unknown_session_empty(client):
    r = client.get("/sessions/nope-not-real/messages")
    assert r.status_code == 200
    assert r.json()["messages"] == []
