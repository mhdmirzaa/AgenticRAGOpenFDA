"""
Assemble the LangGraph state graph.  [M6]  rag-agentic Step 4.
Flow: route -> rewrite -> retrieve -> rerank -> grade -> decide -> {generate | rewrite(loop) | refuse}
HARD cap: MAX_ITERS = settings.max_iters (3). Record every decision into state.trace.
Expose run_agent(question) and run_agent_streaming(question).
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, END

from app.agent.state import RagState
from app.agent.nodes import (
    guardrail_node,
    route_node,
    rewrite_node,
    retrieve_node,
    rerank_node,
    grade_node,
    decide_node,
    generate_node,
    refuse_node,
)
from app.config import get_settings
from app.models import Citation, TraceStep
from app.providers.base import get_provider


def _guardrail_decision(state: RagState) -> str:
    """After guardrail: refuse if blocked (unsafe), else continue to route."""
    if state.get("blocked", False):
        return "refuse"
    return "route"


def _route_decision(state: RagState) -> str:
    """After route: go to rewrite if retrieval needed, else refuse."""
    if state.get("needs_retrieval", True):
        return "rewrite"
    return "refuse"


def _decide_decision(state: RagState) -> str:
    """After decide: generate if sufficient, refuse if at cap, else retry."""
    settings = get_settings()
    if state.get("is_sufficient", False):
        return "generate"
    if state.get("iterations", 0) >= settings.max_iters:
        return "refuse"
    return "rewrite"  # loop back


def build_graph() -> StateGraph:
    """Build the agentic RAG state graph."""
    graph = StateGraph(RagState)

    # Add nodes
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("route", route_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("grade", grade_node)
    graph.add_node("decide", decide_node)
    graph.add_node("generate", generate_node)
    graph.add_node("refuse", refuse_node)

    # Set entry point: the safety guardrail runs FIRST, before any retrieval.
    graph.set_entry_point("guardrail")

    # Add edges
    graph.add_conditional_edges("guardrail", _guardrail_decision, {
        "route": "route",
        "refuse": "refuse",
    })
    graph.add_conditional_edges("route", _route_decision, {
        "rewrite": "rewrite",
        "refuse": "refuse",
    })
    graph.add_edge("rewrite", "retrieve")
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "grade")
    graph.add_edge("grade", "decide")
    graph.add_conditional_edges("decide", _decide_decision, {
        "generate": "generate",
        "refuse": "refuse",
        "rewrite": "rewrite",
    })
    graph.add_edge("generate", END)
    graph.add_edge("refuse", END)

    return graph


# Compiled graph singleton
_compiled_graph = None


def get_compiled_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        graph = build_graph()
        _compiled_graph = graph.compile()
    return _compiled_graph


def _initial_state(question: str, use_hybrid: bool,
                   use_scoping: bool | None = None) -> RagState:
    """Build a fresh initial state for a run."""
    if use_scoping is None:
        use_scoping = get_settings().enable_scoping
    return {
        "question": question,
        "query": "",
        "candidates": [],
        "graded": [],
        "iterations": 0,
        "answer": "",
        "citations": [],
        "trace": [],
        "trace_id": str(uuid.uuid4()),
        "needs_retrieval": True,
        "is_sufficient": False,
        "refused": False,
        "use_hybrid": use_hybrid,
        "use_scoping": use_scoping,
        "scope": {},
        "scope_path": "",
        "blocked": False,
        "block_category": "",
        "block_message": "",
    }


def _persist_trace(state: RagState) -> None:
    """Store the trace so GET /api/trace/{id} can serve it."""
    from app.api.trace import store_trace
    trace_id = state.get("trace_id", "")
    if trace_id:
        store_trace(trace_id, state.get("trace", []))


async def run_agent(question: str, use_hybrid: bool = False,
                    use_scoping: bool | None = None) -> RagState:
    """Run the full agent pipeline (non-streaming). Returns final state.

    `use_scoping` toggles metadata-scoped retrieval (defaults to the config
    setting); the eval harness sets it explicitly to isolate scoping's effect.
    """
    compiled = get_compiled_graph()
    final_state = await compiled.ainvoke(
        _initial_state(question, use_hybrid, use_scoping))
    _persist_trace(final_state)
    return final_state


async def _contextualize(question: str, history: list[dict] | None) -> str:
    """Resolve coreferences in a follow-up against prior turns.

    Turns "what are the warnings for it?" into a standalone question ("...for
    ibuprofen?") so route/rewrite/retrieve see an explicit query. No history ->
    the question is returned unchanged (and no LLM call is made). Any failure
    degrades to the original question so memory never breaks a request.
    """
    hist_block = _format_history(history)
    if not hist_block:
        return question
    from app.agent.prompts import CONTEXTUALIZE_PROMPT
    try:
        provider = get_provider()
        standalone = await provider.complete(
            CONTEXTUALIZE_PROMPT.format(history=hist_block, question=question)
        )
        standalone = standalone.strip().strip('"').strip("'")
        return standalone or question
    except Exception:
        return question


def _evidence_payload(state: RagState) -> dict:
    """Build the graded-candidate evidence set (PASS/FAIL per chunk) for the UI."""
    graded_ids = {c["chunk_id"] for c in state.get("graded", [])}
    chunks = []
    for c in state.get("candidates", []):
        chunks.append({
            "chunk_id": c.get("chunk_id", ""),
            "source": c.get("source", ""),
            "section": c.get("section", ""),
            "section_title": c.get("section_title", ""),
            "text": (c.get("text", "") or "")[:400],
            "source_url": c.get("source_url", ""),
            "grade": "PASS" if c.get("chunk_id") in graded_ids else "FAIL",
        })
    return {"type": "evidence", "chunks": chunks}


async def _run_agent_events(
    question: str, use_hybrid: bool, history: list[dict] | None = None
):
    """Drive guardrail -> route -> (rewrite..decide) loop, yielding UI events.

    An async generator that yields lightweight ("stage"/"evidence", payload)
    tuples in real time as each node runs, then finally ("decision", state) with
    `state["_next"]` set to "generate", "refuse", or "blocked". Reuses the exact
    node functions the compiled graph uses (no duplicated logic).

    When `history` is present the question is first contextualized (coreference
    resolution) so follow-ups retrieve against the right drug.
    """
    from app.agent.nodes import (
        guardrail_node, route_node, rewrite_node, retrieve_node,
        rerank_node, grade_node, decide_node,
    )

    question = await _contextualize(question, history)
    state: RagState = _initial_state(question, use_hybrid)

    # 1) Safety guardrail (first, before any retrieval).
    yield ("stage", {"type": "stage", "stage": "safety", "status": "active",
                     "detail": "Safety check"})
    state.update(await guardrail_node(state))
    if _guardrail_decision(state) == "refuse":
        yield ("stage", {"type": "stage", "stage": "blocked", "status": "done",
                         "detail": f"Blocked: {state.get('block_category', '')}"})
        state["_next"] = "blocked"
        yield ("decision", state)
        return
    yield ("stage", {"type": "stage", "stage": "safety", "status": "done",
                     "detail": "Safe to answer"})

    # 2) Route.
    yield ("stage", {"type": "stage", "stage": "route", "status": "active",
                     "detail": "Understanding the question"})
    state.update(await route_node(state))
    if _route_decision(state) == "refuse":
        yield ("stage", {"type": "stage", "stage": "route", "status": "done",
                         "detail": "Off-topic — cannot answer"})
        state["_next"] = "refuse"
        yield ("decision", state)
        return
    yield ("stage", {"type": "stage", "stage": "route", "status": "done",
                     "detail": "Needs FDA-label search"})

    # 3) Retrieval / grading loop.
    scope_emitted = False
    while True:
        yield ("stage", {"type": "stage", "stage": "search", "status": "active",
                         "detail": "Searching FDA labels"})
        state.update(await rewrite_node(state))
        state.update(await retrieve_node(state))
        state.update(await rerank_node(state))
        # Surface the resolved drug scope once (metadata-scoped retrieval): the
        # evidence panel shows "Scope: doxycycline" or "Scope: all".
        if not scope_emitted:
            scope_emitted = True
            scope = state.get("scope") or {}
            yield ("stage", {"type": "stage", "stage": "scope", "status": "done",
                             "detail": f"Scope: {scope.get('display', 'all')}"})
        yield ("stage", {"type": "stage", "stage": "search", "status": "done",
                         "detail": f"Found {len(state.get('candidates', []))} candidates"})

        yield ("stage", {"type": "stage", "stage": "grade", "status": "active",
                         "detail": "Grading evidence"})
        state.update(await grade_node(state))
        yield ("evidence", _evidence_payload(state))
        yield ("stage", {"type": "stage", "stage": "grade", "status": "done",
                         "detail": f"{len(state.get('graded', []))} passed"})

        state.update(await decide_node(state))
        decision = _decide_decision(state)
        yield ("stage", {"type": "stage", "stage": "decide", "status": "done",
                         "detail": decision if decision != "rewrite" else "Re-retrieving"})
        if decision != "rewrite":
            state["_next"] = decision  # "generate" or "refuse"
            yield ("decision", state)
            return


async def run_agent_answer(
    question: str, history: list[dict] | None = None, use_hybrid: bool = True
) -> dict:
    """Non-streaming agentic answer (course-parity /ask-agentic + Telegram).

    Runs the full guardrail->route->loop->generate/refuse pipeline and returns
    a plain dict: {answer, citations, trace_id, refused, blocked}.
    """
    from app.agent.nodes import _extract_citations, generate_node, refuse_node
    from app.retrieval.cache import get_cached_answer, store_cached_answer

    mode = "optimized" if use_hybrid else "baseline"
    # Exact-repeat, stateless questions return the whole answer instantly.
    # History-bearing follow-ups are never served from cache (the standalone
    # question — and thus the answer — depends on prior turns).
    if not history:
        cached = get_cached_answer(question, mode, kind="ans")
        if cached is not None:
            return cached

    state: RagState | None = None
    async for kind, payload in _run_agent_events(question, use_hybrid, history):
        if kind == "decision":
            state = payload
    assert state is not None

    nxt = state.get("_next")
    if nxt in ("refuse", "blocked"):
        state.update(await refuse_node(state))
    else:
        state.update(await generate_node(state))
    _persist_trace(state)

    citations = state.get("citations", [])
    result = {
        "answer": state.get("answer", ""),
        "citations": [c.model_dump() if hasattr(c, "model_dump") else c
                      for c in citations],
        "trace_id": state.get("trace_id", ""),
        "refused": bool(state.get("refused", False)),
        "blocked": bool(state.get("blocked", False)),
    }
    # Cache stateless answers (blocked verdicts too — they're deterministic).
    if not history:
        store_cached_answer(question, mode, result, kind="ans")
    return result


def _format_history(history: list[dict] | None) -> str:
    """Render prior turns as a compact conversation-memory block (or empty)."""
    if not history:
        return ""
    lines = []
    for m in history:
        role = "User" if m.get("role") == "user" else "Assistant"
        content = (m.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    if not lines:
        return ""
    return "Prior conversation (for context on follow-up questions only):\n" + "\n".join(lines) + "\n\n"


async def run_agent_streaming(
    question: str, use_hybrid: bool = False, history: list[dict] | None = None
) -> AsyncGenerator[dict, None]:
    """Run the agent and stream the answer. Yields type: token|done|error.

    The retrieval/grading loop runs to completion first (it must, before a
    grounded answer exists), then the FINAL generation LLM call is streamed
    token-by-token straight from the provider.

    `history` (last-N prior messages) is injected into the generation prompt as
    conversation memory for follow-up questions.
    """
    import time

    from app.agent.nodes import _extract_citations
    from app.agent.prompts import GENERATE_PROMPT, REFUSE_PROMPT
    from app.providers.base import get_provider
    from app.observability import get_observer, estimate_tokens, estimate_cost

    observer = get_observer()
    lf_trace = observer.start_trace(
        "chat", input=question, metadata={"hybrid": use_hybrid}
    )

    def _log_node_spans(state: RagState) -> None:
        """Mirror the agent's decision trace into Langfuse (one span per node)."""
        for step in state.get("trace", []):
            node = getattr(step, "node", "")
            lf_trace.span(
                name=node,
                input=getattr(step, "input", ""),
                output=getattr(step, "output", ""),
            )

    try:
        # Drive the agent, forwarding live stage/evidence events to the UI.
        state: RagState | None = None
        async for kind, payload in _run_agent_events(question, use_hybrid, history):
            if kind == "decision":
                state = payload
            else:  # "stage" | "evidence"
                yield payload
        assert state is not None

        # The loop may have contextualized a follow-up into a standalone
        # question; use that resolved form for generation + memory too.
        question = state.get("question", question)
        trace_id = state.get("trace_id", "")

        nxt = state.get("_next")
        if nxt in ("refuse", "blocked"):
            blocked = nxt == "blocked"
            # Terminal stage for the UI timeline. `blocked` was already emitted
            # by the guardrail; a plain (unanswerable) refusal needs its own.
            if not blocked:
                yield {"type": "stage", "stage": "refuse", "status": "done",
                       "detail": "The indexed FDA labels don't cover this."}
            refusal_text = (state.get("block_message") or REFUSE_PROMPT) if blocked \
                else REFUSE_PROMPT
            state["answer"] = refusal_text
            state["refused"] = True
            state["citations"] = []
            state["trace"] = state.get("trace", []) + [TraceStep(
                node="refuse", input=question,
                output=(f"blocked: {state.get('block_category','')}" if blocked
                        else "refused - insufficient relevant information"),
            )]
            _persist_trace(state)
            _log_node_spans(state)
            lf_trace.update(output=refusal_text,
                            metadata={"refused": True, "blocked": blocked})
            lf_trace.end()
            for word in refusal_text.split(" "):
                yield {"type": "token", "text": word + " "}
            yield {"type": "done", "citations": [], "trace_id": trace_id,
                   "refused": True, "blocked": blocked}
            return

        # Sufficient evidence -> stream the grounded generation.
        graded = state.get("graded", [])
        yield {"type": "stage", "stage": "generate", "status": "active",
               "detail": "Composing a cited answer from graded evidence."}
        context_parts = [
            f"[{i}] Source: {c['source']}#{c['section']}\n{c['text']}"
            for i, c in enumerate(graded, 1)
        ]
        prompt = _format_history(history) + GENERATE_PROMPT.format(
            question=question, context="\n\n---\n\n".join(context_parts)
        )

        provider = get_provider()
        answer_parts: list[str] = []
        _gen_start = time.perf_counter()
        try:
            async for token in provider.generate_stream(prompt):
                answer_parts.append(token)
                yield {"type": "token", "text": token}
        except Exception as gen_err:  # noqa: BLE001
            # Generation outage mid-stream: if nothing was emitted yet, degrade
            # to a clean spoken refusal + a refused `done` (never a raw error).
            logger.warning("generation stream failed: %s", gen_err)
            if not answer_parts:
                from app.agent.prompts import GENERATION_UNAVAILABLE_MESSAGE
                for word in GENERATION_UNAVAILABLE_MESSAGE.split(" "):
                    yield {"type": "token", "text": word + " "}
                lf_trace.update(output="generation-unavailable",
                                metadata={"refused": True, "error": str(gen_err)})
                lf_trace.end()
                yield {"type": "done", "citations": [], "trace_id": trace_id,
                       "refused": True, "blocked": False}
                return
            # Partial answer already streamed: stop cleanly and finalize below.
        _gen_latency_ms = round((time.perf_counter() - _gen_start) * 1000, 1)

        answer = "".join(answer_parts)
        citations = _extract_citations(answer, graded)

        state["answer"] = answer
        state["citations"] = citations
        state["refused"] = False
        state["trace"] = state.get("trace", []) + [TraceStep(
            node="generate",
            input=f"question={question}, chunks={len(graded)} (streamed)",
            output=f"answer_len={len(answer)}, citations={len(citations)}",
        )]
        _persist_trace(state)

        # Observability: node spans + a generation span with token/cost/latency.
        _log_node_spans(state)
        _in_tok = estimate_tokens(prompt)
        _out_tok = estimate_tokens(answer)
        _model = get_settings().gen_model
        lf_trace.span(
            name="generate",
            input=prompt,
            output=answer,
            metadata={
                "chunk_ids": [c.get("chunk_id") for c in graded],
                "tokens_in": _in_tok,
                "tokens_out": _out_tok,
                "cost_usd_est": estimate_cost(_model, _in_tok, _out_tok),
                "latency_ms": _gen_latency_ms,
                "model": _model,
            },
        )
        lf_trace.update(output=answer, metadata={"citations": len(citations)})
        lf_trace.end()

        yield {
            "type": "done",
            "citations": [c.model_dump() if hasattr(c, "model_dump") else c
                          for c in citations],
            "trace_id": trace_id,
            "refused": False,
            "blocked": False,
        }

    except Exception as e:
        # Last-resort guard: log the raw error, surface a friendly message only.
        logger.exception("chat stream failed")
        yield {"type": "error",
               "message": "Something went wrong while answering. "
                          "Please try again in a moment."}
