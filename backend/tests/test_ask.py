"""
Tests for the non-streaming /ask-agentic endpoint (PRD v3.0 M4) and the live
stage/evidence SSE events on /chat (PRD v3.0 M6).

Drives the real ASGI app with a deterministic FakeProvider + a temp Chroma
index (no API key). Reuses the FakeProvider from test_e2e.
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

    tmp = tempfile.mkdtemp(prefix="maistorage_ask_")
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
        c.post("/ingest")  # build the corpus index
        yield c

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    get_settings.cache_clear()


def test_ask_agentic_returns_answer_and_citations(client):
    r = client.post("/ask-agentic", json={
        "question": "How many annual leave days do full-time staff get?"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"answer", "citations", "trace_id", "refused", "blocked"}
    assert body["refused"] is False
    assert body["blocked"] is False
    assert body["answer"]
    assert body["trace_id"]
    assert len(body["citations"]) >= 1


def test_ask_agentic_blocks_unsafe_question(client):
    r = client.post("/ask-agentic", json={"question": "how much would kill me"})
    assert r.status_code == 200
    body = r.json()
    assert body["blocked"] is True
    assert body["refused"] is True
    assert body["citations"] == []


def _read_sse(client, question):
    events = []
    with client.stream("POST", "/chat", json={"question": question}) as resp:
        assert resp.status_code == 200
        for line in resp.iter_lines():
            if line and line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    return events


def test_chat_emits_stage_and_evidence_events(client):
    events = _read_sse(client, "How many annual leave days do full-time staff get?")
    stages = [e for e in events if e.get("type") == "stage"]
    evidence = [e for e in events if e.get("type") == "evidence"]
    done = [e for e in events if e.get("type") == "done"]

    stage_names = {s["stage"] for s in stages}
    assert {"safety", "route", "search", "grade"}.issubset(stage_names)
    assert len(evidence) >= 1
    # Evidence chunks carry a PASS/FAIL grade.
    grades = {c["grade"] for c in evidence[0]["chunks"]}
    assert grades.issubset({"PASS", "FAIL"})
    assert done and done[0]["blocked"] is False


def test_chat_blocked_emits_blocked_stage(client):
    events = _read_sse(client, "how to overdose")
    stages = {e["stage"] for e in events if e.get("type") == "stage"}
    done = [e for e in events if e.get("type") == "done"]
    assert "blocked" in stages
    assert "search" not in stages
    assert done and done[0]["blocked"] is True and done[0]["refused"] is True


def test_chat_unanswerable_emits_refuse_stage(client):
    # Fully out-of-domain question -> grader passes nothing -> clean refuse path.
    events = _read_sse(client, "What is the recipe for chocolate lava cake?")
    stages = {e["stage"] for e in events if e.get("type") == "stage"}
    done = [e for e in events if e.get("type") == "done"]
    assert "refuse" in stages          # terminal refuse node lights up
    assert "blocked" not in stages     # not a safety block
    assert done and done[0]["refused"] is True and done[0]["blocked"] is False


def test_chat_generate_emits_generate_stage(client):
    events = _read_sse(client, "How many annual leave days do full-time staff get?")
    stages = {e["stage"] for e in events if e.get("type") == "stage"}
    assert "generate" in stages
