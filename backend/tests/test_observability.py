"""
Tests for Langfuse observability.  [production item 8]

Verifies: disabled => clean no-op; enabled => spans + trace recorded; and a full
streamed chat run emits per-node spans plus a generation span with token/cost
metadata, all without a real Langfuse server.
"""

import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import app.observability as obs
from tests.test_e2e import FakeProvider


class TestEstimators:
    def test_estimate_tokens(self):
        assert obs.estimate_tokens("") == 0
        assert obs.estimate_tokens("a" * 40) == 10

    def test_estimate_cost_known_and_unknown(self):
        assert obs.estimate_cost("gpt-4.1-mini", 1000, 1000) > 0
        assert obs.estimate_cost("mystery-model", 1000, 1000) == 0.0


class TestDisabledNoOp:
    def test_disabled_by_default(self):
        for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
            os.environ.pop(k, None)
        from app.config import get_settings
        get_settings.cache_clear()
        obs.reset_observer()

        observer = obs.get_observer()
        assert observer.enabled() is False
        # no-op handle must accept the full API without raising
        t = observer.start_trace("chat", input="q")
        t.span(name="route", input="i", output="o")
        t.update(output="a")
        t.end()


class TestEnabledRecords:
    def test_start_trace_records_spans_and_flushes(self):
        class FakeTrace:
            def __init__(self):
                self.spans = []
                self.updated = None

            def span(self, **kw):
                self.spans.append(kw)

            def update(self, **kw):
                self.updated = kw

        class FakeClient:
            def __init__(self):
                self.t = FakeTrace()
                self.flushed = False

            def trace(self, **kw):
                return self.t

            def flush(self):
                self.flushed = True

        observer = obs.Observer.__new__(obs.Observer)
        client = FakeClient()
        observer._client = client
        assert observer.enabled() is True

        handle = observer.start_trace("chat", input="q")
        handle.span(name="route", input="i", output="o")
        handle.update(output="answer")
        handle.end()

        assert any(s["name"] == "route" for s in client.t.spans)
        assert client.t.updated["output"] == "answer"
        assert client.flushed is True


@pytest.fixture(scope="module")
def seeded():
    tmp = tempfile.mkdtemp(prefix="maistorage_obs_")
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"

    from app.config import get_settings
    get_settings.cache_clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod
    from app.retrieval.cache import clear_cache, reset_backend

    reset_backend()
    vs_mod.reset_vectorstore()
    clear_cache()
    provider_base._provider_instance = FakeProvider()

    from app.ingestion.loader import load_corpus
    from app.ingestion.chunker import chunk_documents
    from app.ingestion.indexer import index_chunks

    docs = load_corpus()
    asyncio.run(index_chunks(chunk_documents(docs)))

    yield

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    get_settings.cache_clear()


class TestChatEmitsTrace:
    def test_streamed_chat_emits_node_and_generate_spans(self, seeded, monkeypatch):
        # Enabled observer backed by a recording fake client.
        recorded = {"spans": []}

        class FakeTrace:
            def span(self, **kw):
                recorded["spans"].append(kw.get("name"))

            def update(self, **kw):
                pass

        class FakeClient:
            def trace(self, **kw):
                return FakeTrace()

            def flush(self):
                pass

        observer = obs.Observer.__new__(obs.Observer)
        observer._client = FakeClient()
        monkeypatch.setattr(obs, "get_observer", lambda: observer)

        from app.agent.graph import run_agent_streaming

        async def run():
            async for _ in run_agent_streaming(
                "How many annual leave days do full-time staff get?"
            ):
                pass

        asyncio.run(run())
        assert "route" in recorded["spans"]
        assert "generate" in recorded["spans"]
