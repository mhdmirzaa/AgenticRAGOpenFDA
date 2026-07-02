"""
HTTP-level end-to-end tests through the real ASGI app.  [M3/M6/M8]

Drives the actual FastAPI application (lifespan warm-up, routers, SSE framing)
with a deterministic FakeProvider injected, over the wire via TestClient:
    GET  /health   -> healthy + cache stats
    POST /ingest   -> builds the index
    POST /chat     -> real SSE stream (token... done) with a trace_id
    GET  /trace/id -> the persisted decision trace
No API key required.
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

    tmp = tempfile.mkdtemp(prefix="maistorage_http_")
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"

    from app.config import get_settings
    get_settings.cache_clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod
    vs_mod.reset_vectorstore()
    provider_base._provider_instance = FakeProvider()

    from app.main import app
    with TestClient(app) as c:
        yield c

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    get_settings.cache_clear()


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("healthy", "degraded")
    assert "provider" in body
    assert "embedding_cache" in body


def test_ingest_builds_index(client):
    r = client.post("/ingest")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["chunks_indexed"] > 0


def _read_sse(client, question: str):
    events = []
    with client.stream("POST", "/chat", json={"question": question, "optimized": False}) as resp:
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        for line in resp.iter_lines():
            if line and line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def test_chat_streams_and_persists_trace(client):
    # index must exist first
    client.post("/ingest")
    events = _read_sse(client, "How many annual leave days do full-time staff get?")

    tokens = [e for e in events if e["type"] == "token"]
    done = [e for e in events if e["type"] == "done"]
    assert len(tokens) >= 1
    assert len(done) == 1

    trace_id = done[0]["trace_id"]
    assert trace_id

    r = client.get(f"/trace/{trace_id}")
    assert r.status_code == 200
    trace = r.json()
    assert trace["trace_id"] == trace_id
    nodes = [s["node"] for s in trace["steps"]]
    assert "retrieve" in nodes and "grade" in nodes


def test_trace_404_for_unknown_id(client):
    r = client.get("/trace/does-not-exist")
    assert r.status_code == 404
