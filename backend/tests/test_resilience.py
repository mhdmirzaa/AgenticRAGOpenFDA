"""
Error-handling & resilience (ENHANCE item 5).

Every subsystem outage must degrade to a clean refusal (or a safe default),
never crash the turn or surface a raw error:
  - route LLM down       -> default to attempting retrieval;
  - rewrite LLM down      -> fall back to the raw question as the query;
  - retrieval/embed down  -> zero candidates (loop then refuses);
  - grader LLM down        -> chunk fails closed (excluded);
  - generation LLM down    -> graceful, disclaimer-bearing refusal (refused=True).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.agent.nodes import (
    route_node, rewrite_node, retrieve_node, grade_node, generate_node,
)
from app.agent.prompts import GENERATION_UNAVAILABLE_MESSAGE


class _Boom:
    """A provider whose every LLM call raises (simulates a timeout/outage)."""
    async def complete(self, prompt):
        raise RuntimeError("llm timeout")

    async def embed(self, text):
        raise RuntimeError("embed service down")

    async def embed_batch(self, texts):
        raise RuntimeError("embed service down")

    async def generate_stream(self, prompt):
        raise RuntimeError("llm timeout")
        yield  # pragma: no cover - unreachable


def _inject(provider):
    from app.providers import base as provider_base
    provider_base._provider_instance = provider


def _reset():
    from app.providers import base as provider_base
    provider_base.reset_provider()


def _run(coro):
    _inject(_Boom())
    try:
        return asyncio.run(coro)
    finally:
        _reset()


def test_route_llm_down_defaults_to_retrieve():
    out = _run(route_node({"question": "what are warnings for ibuprofen",
                           "trace": []}))
    assert out["needs_retrieval"] is True  # safe degrade, no exception


def test_rewrite_llm_down_falls_back_to_question():
    q = "what are the warnings for ibuprofen"
    out = _run(rewrite_node({"question": q, "trace": []}))
    assert out["query"] == q  # never empty, never crashes


def test_retrieval_outage_degrades_to_zero_candidates():
    # Offline (no OpenSearch) + embed down -> _compute raises -> caught -> [].
    from app.retrieval.cache import clear_cache
    clear_cache()
    out = _run(retrieve_node({"question": "ibuprofen warnings",
                              "query": "ibuprofen warnings",
                              "use_hybrid": False, "trace": []}))
    assert out["candidates"] == []


def test_grader_outage_fails_chunk_closed():
    candidates = [{"chunk_id": "c1", "text": "some text",
                   "source": "IBUPROFEN", "section": "warnings"}]
    out = _run(grade_node({"question": "ibuprofen warnings",
                           "candidates": candidates, "trace": []}))
    assert out["graded"] == []  # unverifiable evidence is excluded


def test_generation_outage_returns_graceful_refusal():
    graded = [{"chunk_id": "c1", "text": "IBUPROFEN warnings ...",
               "source": "IBUPROFEN", "section": "warnings"}]
    out = _run(generate_node({"question": "ibuprofen warnings",
                              "graded": graded, "trace": []}))
    assert out["refused"] is True
    assert out["citations"] == []
    assert out["answer"] == GENERATION_UNAVAILABLE_MESSAGE
    assert "healthcare professional" in out["answer"]  # disclaimer preserved


def test_full_turn_survives_total_llm_outage_as_refusal():
    """With the whole LLM down, /ask-agentic-style run still returns cleanly."""
    from app.agent.graph import run_agent_answer
    _inject(_Boom())
    try:
        result = asyncio.run(run_agent_answer("what are warnings for ibuprofen"))
    finally:
        _reset()
    # No exception; a clean refusal payload with the disclaimer, not a 500.
    assert result["refused"] is True
    assert result["citations"] == []
    assert "healthcare professional" in result["answer"]
