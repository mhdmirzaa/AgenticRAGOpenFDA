"""
Assemble the LangGraph state graph.  [M6]  rag-agentic Step 4.
Flow: route -> rewrite -> retrieve -> rerank -> grade -> decide -> {generate | rewrite(loop) | refuse}
HARD cap: MAX_ITERS = settings.max_iters (3). Record every decision into state.trace.
Expose run_agent(question) and run_agent_streaming(question).
"""

from __future__ import annotations

import uuid
from typing import AsyncGenerator

from langgraph.graph import StateGraph, END

from app.agent.state import RagState
from app.agent.nodes import (
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
    graph.add_node("route", route_node)
    graph.add_node("rewrite", rewrite_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("rerank", rerank_node)
    graph.add_node("grade", grade_node)
    graph.add_node("decide", decide_node)
    graph.add_node("generate", generate_node)
    graph.add_node("refuse", refuse_node)

    # Set entry point
    graph.set_entry_point("route")

    # Add edges
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


def _initial_state(question: str, use_hybrid: bool) -> RagState:
    """Build a fresh initial state for a run."""
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
    }


def _persist_trace(state: RagState) -> None:
    """Store the trace so GET /api/trace/{id} can serve it."""
    from app.api.trace import store_trace
    trace_id = state.get("trace_id", "")
    if trace_id:
        store_trace(trace_id, state.get("trace", []))


async def run_agent(question: str, use_hybrid: bool = False) -> RagState:
    """Run the full agent pipeline (non-streaming). Returns final state."""
    compiled = get_compiled_graph()
    final_state = await compiled.ainvoke(_initial_state(question, use_hybrid))
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


async def _run_loop_to_decision(
    question: str, use_hybrid: bool, history: list[dict] | None = None
) -> RagState:
    """Run route -> (rewrite -> retrieve -> rerank -> grade -> decide) loop.

    Reuses the exact node functions and decision helpers the compiled graph
    uses (no duplicated logic), stopping just before generate/refuse so the
    final generation can be streamed token-by-token.

    When `history` is present, the question is first contextualized (coreference
    resolution) so follow-up questions retrieve against the right drug.
    """
    from app.agent.nodes import (
        route_node, rewrite_node, retrieve_node,
        rerank_node, grade_node, decide_node,
    )

    question = await _contextualize(question, history)
    state: RagState = _initial_state(question, use_hybrid)
    state.update(await route_node(state))
    if _route_decision(state) == "refuse":
        state["_next"] = "refuse"
        return state

    while True:
        state.update(await rewrite_node(state))
        state.update(await retrieve_node(state))
        state.update(await rerank_node(state))
        state.update(await grade_node(state))
        state.update(await decide_node(state))
        decision = _decide_decision(state)
        if decision != "rewrite":
            state["_next"] = decision  # "generate" or "refuse"
            return state


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
        state = await _run_loop_to_decision(question, use_hybrid, history)
        # The loop may have contextualized a follow-up into a standalone
        # question; use that resolved form for generation + memory too.
        question = state.get("question", question)
        trace_id = state.get("trace_id", "")

        if state.get("_next") == "refuse":
            state["answer"] = REFUSE_PROMPT
            state["refused"] = True
            state["citations"] = []
            state["trace"] = state.get("trace", []) + [TraceStep(
                node="refuse", input=question,
                output="refused - insufficient relevant information",
            )]
            _persist_trace(state)
            _log_node_spans(state)
            lf_trace.update(output=REFUSE_PROMPT, metadata={"refused": True})
            lf_trace.end()
            for word in REFUSE_PROMPT.split(" "):
                yield {"type": "token", "text": word + " "}
            yield {"type": "done", "citations": [], "trace_id": trace_id,
                   "refused": True}
            return

        # Sufficient evidence -> stream the grounded generation.
        graded = state.get("graded", [])
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
        async for token in provider.generate_stream(prompt):
            answer_parts.append(token)
            yield {"type": "token", "text": token}
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
        }

    except Exception as e:
        yield {"type": "error", "message": str(e)}
