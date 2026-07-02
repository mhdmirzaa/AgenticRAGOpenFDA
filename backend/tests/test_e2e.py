"""
End-to-end / integration tests for the full agentic RAG pipeline.  [M6/M7]

Runs the WHOLE system offline against a real Chroma index built with local
sentence-transformers embeddings, driven by a deterministic FakeProvider that
stands in for the chat LLM (route/rewrite/grade/generate). This exercises the
real graph, hybrid retrieval, citation extraction, refusal path, streaming, and
the trace store -- no API key required.

Generation quality is NOT asserted here (that needs a real LLM); wiring and
control-flow ARE.
"""

import asyncio
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class FakeProvider:
    """Deterministic stand-in: real MiniLM embeddings, rule-based generation."""

    def __init__(self):
        from app.providers.local import LocalProvider
        os.environ.setdefault("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self._embedder = LocalProvider("sentence-transformers/all-MiniLM-L6-v2")

    async def embed(self, text):
        return await self._embedder.embed(text)

    async def embed_batch(self, texts):
        return await self._embedder.embed_batch(texts)

    def _reply(self, prompt: str) -> str:
        p = prompt.lower()
        if "query router" in p:
            return "RETRIEVE"
        if "search query optimizer" in p:
            # Echo the original question as the query.
            q = prompt.split("Original question:", 1)[-1].split("\n", 1)[0].strip()
            return q or "query"
        if "relevance grader" in p:
            # YES if the question shares a meaningful word with the chunk.
            question = prompt.split("Question:", 1)[-1].split("Chunk:", 1)[0].lower()
            chunk = prompt.split("Chunk:", 1)[-1].lower()
            stop = {"the", "a", "an", "of", "is", "do", "how", "many", "what",
                    "for", "to", "in", "my", "i", "get", "and", "does", "are",
                    "can", "at", "this", "that", "on", "if"}
            words = {w.strip("?.,") for w in question.split() if len(w) > 3 and w not in stop}
            return "YES" if any(w in chunk for w in words) else "NO"
        if "context chunks" in p:
            # Generation prompt -> produce an answer that cites chunk [1].
            return "Based on the provided context, here is the answer [1]."
        return "ok"

    async def complete(self, prompt):
        return self._reply(prompt)

    async def generate_stream(self, prompt):
        for tok in self._reply(prompt).split(" "):
            yield tok + " "


@pytest.fixture(scope="module")
def seeded_system():
    """Build a temp Chroma index + inject the FakeProvider for the whole module."""
    tmp = tempfile.mkdtemp(prefix="maistorage_e2e_")
    os.environ["CHROMA_PATH"] = tmp
    os.environ["LLM_PROVIDER"] = "local"

    from app.config import get_settings
    get_settings.cache_clear()

    from app.providers import base as provider_base
    from app.retrieval import vectorstore as vs_mod
    from app.retrieval.cache import clear_cache

    vs_mod.reset_vectorstore()
    clear_cache()

    fake = FakeProvider()
    provider_base._provider_instance = fake  # inject

    # Build the index from the real corpus.
    from app.ingestion.loader import load_corpus
    from app.ingestion.chunker import chunk_documents
    from app.ingestion.indexer import index_chunks
    from app.retrieval.hybrid import get_hybrid_retriever

    docs = load_corpus()
    chunks = chunk_documents(docs)
    n = asyncio.run(index_chunks(chunks))
    assert n > 0
    get_hybrid_retriever().ensure_index()

    yield fake

    provider_base.reset_provider()
    vs_mod.reset_vectorstore()
    get_settings.cache_clear()


def test_answerable_question_generates_cited_answer(seeded_system):
    """A known question runs the full loop and returns an answer with a citation."""
    from app.agent.graph import run_agent

    state = asyncio.run(run_agent("How many annual leave days do full-time staff get?"))
    assert state["answer"]
    assert state["refused"] is False
    assert len(state["graded"]) > 0
    assert len(state["citations"]) >= 1
    # Citation must reference a real graded chunk.
    cited_ids = {c.chunk_id for c in state["citations"]}
    graded_ids = {g["chunk_id"] for g in state["graded"]}
    assert cited_ids.issubset(graded_ids)


def test_unanswerable_question_refuses(seeded_system):
    """An out-of-corpus question yields an explicit refusal, no citations."""
    from app.agent.graph import run_agent

    # Fully out-of-domain question (no lexical overlap with the handbook), so the
    # FakeProvider's word-overlap grader returns NO for every chunk -> refusal.
    state = asyncio.run(run_agent("What is the recipe for a chocolate lava cake?"))
    assert state["refused"] is True
    assert state["citations"] == []


def test_iteration_cap_respected(seeded_system):
    """The loop always terminates within the hard cap."""
    from app.agent.graph import run_agent
    from app.config import get_settings

    state = asyncio.run(run_agent("Some totally unrelated cosmic astrophysics question?"))
    assert state["iterations"] <= get_settings().max_iters


def test_trace_is_persisted_and_retrievable(seeded_system):
    """After a run, the trace store serves the trace for that trace_id."""
    from app.agent.graph import run_agent
    from app.api.trace import get_trace

    state = asyncio.run(run_agent("How many public holidays does MaiStorage observe annually?"))
    trace_id = state["trace_id"]
    steps = get_trace(trace_id)
    assert steps is not None
    nodes = [s.node for s in steps]
    assert "route" in nodes and "retrieve" in nodes and "grade" in nodes


def test_streaming_yields_tokens_then_done(seeded_system):
    """The streaming path emits multiple token events then a done event."""
    from app.agent.graph import run_agent_streaming

    async def collect():
        events = []
        async for ev in run_agent_streaming("What encryption does MaiVault use for data at rest?"):
            events.append(ev)
        return events

    events = asyncio.run(collect())
    tokens = [e for e in events if e["type"] == "token"]
    done = [e for e in events if e["type"] == "done"]
    assert len(tokens) >= 1
    assert len(done) == 1
    assert "trace_id" in done[0]


def test_streaming_tokens_are_deltas_without_duplication(seeded_system):
    """The stream must emit DELTAS that concatenate to exactly the answer.

    Guards the streaming contract behind the word-doubling bug: tokens are
    deltas (not cumulative), the assembled text has no consecutive duplicate
    words, and the `done` event does NOT resend the full answer (which a
    frontend would otherwise append again).
    """
    from app.agent.graph import run_agent_streaming

    async def collect():
        toks, done = [], None
        async for ev in run_agent_streaming(
            "How many annual leave days do full-time staff get?"
        ):
            if ev["type"] == "token":
                toks.append(ev["text"])
            elif ev["type"] == "done":
                done = ev
        return toks, done

    tokens, done = asyncio.run(collect())
    assembled = "".join(tokens).strip()

    # FakeProvider's deterministic generation.
    assert assembled == "Based on the provided context, here is the answer [1]."

    # No word rendered twice in a row (the doubling signature).
    words = assembled.split()
    assert not any(a == b for a, b in zip(words, words[1:])), f"duplicated: {assembled}"

    # `done` must not resend the answer text (frontend would append it again).
    assert "answer" not in done


def test_hybrid_mode_runs_end_to_end(seeded_system):
    """Optimized (hybrid+BM25) mode completes and retrieves chunks."""
    from app.agent.graph import run_agent

    state = asyncio.run(run_agent("What is MaiSync's maximum file size per file?", use_hybrid=True))
    assert state["answer"]
    assert len(state["graded"]) > 0
    # The retrieve trace step should record hybrid mode.
    retrieve_steps = [s for s in state["trace"] if s.node == "retrieve"]
    assert any("hybrid" in s.input for s in retrieve_steps)


def test_embedding_cache_records_hits(seeded_system):
    """Re-embedding the same query hits the cache."""
    from app.retrieval.cache import cached_embed, cache_stats, clear_cache

    clear_cache()
    asyncio.run(cached_embed("repeated query"))
    asyncio.run(cached_embed("repeated query"))
    stats = cache_stats()
    assert stats["hits"] >= 1
