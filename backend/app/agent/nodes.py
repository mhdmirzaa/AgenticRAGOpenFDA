"""
LangGraph nodes.  [M6]  rag-agentic Steps 3-5.
route, rewrite, retrieve, rerank, grade, decide, generate/refuse.
Only graded chunks reach generate. Empty graded set -> refuse.
Post-validate citations against graded chunk_ids.
"""

from __future__ import annotations

import re
import uuid

from app.agent.state import RagState
from app.agent.prompts import (
    ROUTE_PROMPT,
    REWRITE_PROMPT,
    GRADE_PROMPT,
    GENERATE_PROMPT,
    REFUSE_PROMPT,
)
from app.config import get_settings
from app.models import Citation, TraceStep
from app.providers.base import get_provider
from app.retrieval.vectorstore import get_vectorstore


async def route_node(state: RagState) -> dict:
    """Decide if the question needs retrieval or should be refused."""
    provider = get_provider()
    question = state["question"]

    prompt = ROUTE_PROMPT.format(question=question)
    response = await provider.complete(prompt)
    decision = response.strip().upper()

    needs_retrieval = "RETRIEVE" in decision

    trace_step = TraceStep(
        node="route",
        input=question,
        output=f"needs_retrieval={needs_retrieval} (raw: {decision})",
    )

    return {
        "needs_retrieval": needs_retrieval,
        "trace": state.get("trace", []) + [trace_step],
        "trace_id": state.get("trace_id", str(uuid.uuid4())),
        "iterations": 0,
    }


async def rewrite_node(state: RagState) -> dict:
    """Rewrite/sharpen the query for better retrieval."""
    provider = get_provider()
    question = state["question"]
    previous_query = state.get("query", "")
    iteration = state.get("iterations", 0)

    prompt = REWRITE_PROMPT.format(
        question=question,
        previous_query=previous_query,
        iteration=iteration,
    )
    rewritten = await provider.complete(prompt)
    rewritten = rewritten.strip().strip('"').strip("'")

    trace_step = TraceStep(
        node="rewrite",
        input=f"question={question}, prev_query={previous_query}, iter={iteration}",
        output=rewritten,
    )

    return {
        "query": rewritten,
        "trace": state.get("trace", []) + [trace_step],
    }


async def retrieve_node(state: RagState) -> dict:
    """Retrieve candidates from the vector store.

    Optimized mode (use_hybrid) merges dense + BM25 via RRF; baseline mode does
    dense-only similarity search. Query embeddings are cached across retries.
    """
    settings = get_settings()
    query = state.get("query", state["question"])
    use_hybrid = state.get("use_hybrid", False)
    mode = "hybrid(dense+BM25)" if use_hybrid else "dense"

    async def _compute() -> list[dict]:
        out: list[dict] = []
        if use_hybrid:
            from app.retrieval.hybrid import get_hybrid_retriever
            retriever = get_hybrid_retriever()
            retriever.ensure_index()
            merged = await retriever.retrieve(query, top_k=settings.top_k)
            for r in merged:
                meta = r.metadata or {}
                out.append({
                    "chunk_id": r.chunk_id, "text": r.text, "source": r.source,
                    "section": r.section, "score": r.rrf_score,
                    "source_url": meta.get("source_url", ""),
                    "section_title": meta.get("section_title", ""),
                })
        else:
            from app.retrieval.cache import cached_embed
            query_embedding = await cached_embed(query)
            vs = get_vectorstore()
            results = vs.query(query_embedding, n_results=settings.top_k)
            for r in results:
                meta = r.metadata or {}
                out.append({
                    "chunk_id": r.chunk_id, "text": r.text, "source": r.source,
                    "section": r.section, "score": r.score,
                    "source_url": meta.get("source_url", ""),
                    "section_title": meta.get("section_title", ""),
                })
        return out

    # Retrieval-results cache (item 7): repeated (mode, query) skips embed+search.
    from app.retrieval.cache import cached_retrieval
    candidates = await cached_retrieval(query, mode, _compute)

    trace_step = TraceStep(
        node="retrieve",
        input=f"query={query}, top_k={settings.top_k}, mode={mode}",
        output=f"found {len(candidates)} candidates: {[c['chunk_id'] for c in candidates]}",
    )

    return {
        "candidates": candidates,
        "trace": state.get("trace", []) + [trace_step],
    }


async def rerank_node(state: RagState) -> dict:
    """Rerank candidates.

    Optimized mode (use_hybrid) runs a local cross-encoder over the merged
    candidates and keeps top-n. Baseline mode just truncates to top-n by the
    dense similarity score (no cross-encoder), keeping the two modes distinct.
    """
    settings = get_settings()
    candidates = state.get("candidates", [])
    query = state.get("query", state["question"])
    use_hybrid = state.get("use_hybrid", False)

    if not use_hybrid:
        reranked_dicts = sorted(
            candidates, key=lambda c: c.get("score", 0), reverse=True
        )[:settings.rerank_top_n]
        trace_step = TraceStep(
            node="rerank",
            input=f"{len(candidates)} candidates (baseline: score-truncate)",
            output=f"kept {len(reranked_dicts)}: {[c['chunk_id'] for c in reranked_dicts]}",
        )
        return {
            "candidates": reranked_dicts,
            "trace": state.get("trace", []) + [trace_step],
        }

    try:
        from app.retrieval.reranker import rerank as do_rerank
        from app.retrieval.vectorstore import RetrievedChunk

        # Convert dicts to RetrievedChunk for reranker
        chunks = [
            RetrievedChunk(
                chunk_id=c["chunk_id"],
                text=c["text"],
                source=c["source"],
                section=c["section"],
                score=c.get("score", 0),
            )
            for c in candidates
        ]
        reranked = do_rerank(query, chunks, top_n=settings.rerank_top_n)
        # Map back to the original candidate dicts to preserve their metadata
        # (source_url, section_title) which RetrievedChunk conversion dropped.
        by_id = {c["chunk_id"]: c for c in candidates}
        reranked_dicts = []
        for r in reranked:
            base = dict(by_id.get(r.chunk_id, {}))
            base.update({
                "chunk_id": r.chunk_id, "text": r.text, "source": r.source,
                "section": r.section, "score": r.score,
            })
            reranked_dicts.append(base)
    except Exception:
        # Fallback: just take top_n by score
        reranked_dicts = sorted(
            candidates, key=lambda c: c.get("score", 0), reverse=True
        )[:settings.rerank_top_n]

    trace_step = TraceStep(
        node="rerank",
        input=f"{len(candidates)} candidates",
        output=f"kept {len(reranked_dicts)}: {[c['chunk_id'] for c in reranked_dicts]}",
    )

    return {
        "candidates": reranked_dicts,
        "trace": state.get("trace", []) + [trace_step],
    }


async def grade_node(state: RagState) -> dict:
    """Grade each candidate chunk for relevance."""
    provider = get_provider()
    question = state["question"]
    candidates = state.get("candidates", [])

    graded = []
    grade_details = []

    for chunk in candidates:
        prompt = GRADE_PROMPT.format(
            question=question,
            chunk_text=chunk["text"][:1500],
        )
        response = await provider.complete(prompt)
        is_relevant = "YES" in response.strip().upper()

        grade_details.append(f"{chunk['chunk_id']}={'YES' if is_relevant else 'NO'}")

        if is_relevant:
            graded.append(chunk)

    trace_step = TraceStep(
        node="grade",
        input=f"grading {len(candidates)} chunks for: {question}",
        output=f"passed: {len(graded)}/{len(candidates)} | {', '.join(grade_details)}",
    )

    return {
        "graded": graded,
        "trace": state.get("trace", []) + [trace_step],
    }


async def decide_node(state: RagState) -> dict:
    """Decide: enough graded chunks -> generate; else loop or refuse."""
    graded = state.get("graded", [])
    iterations = state.get("iterations", 0)
    settings = get_settings()

    is_sufficient = len(graded) > 0
    at_cap = iterations >= settings.max_iters

    if is_sufficient:
        decision = "generate"
    elif at_cap:
        decision = "refuse (max iterations reached)"
    else:
        decision = "retry retrieval"

    trace_step = TraceStep(
        node="decide",
        input=f"graded={len(graded)}, iterations={iterations}, max={settings.max_iters}",
        output=decision,
    )

    return {
        "is_sufficient": is_sufficient,
        "iterations": iterations + 1,
        "trace": state.get("trace", []) + [trace_step],
    }


async def generate_node(state: RagState) -> dict:
    """Generate answer with citations from graded chunks."""
    provider = get_provider()
    question = state["question"]
    graded = state.get("graded", [])

    # Build context with numbered chunks
    context_parts = []
    for i, chunk in enumerate(graded, 1):
        context_parts.append(
            f"[{i}] Source: {chunk['source']}#{chunk['section']}\n{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = GENERATE_PROMPT.format(question=question, context=context)
    answer = await provider.complete(prompt)

    # Extract and validate citations
    citations = _extract_citations(answer, graded)

    trace_step = TraceStep(
        node="generate",
        input=f"question={question}, chunks={len(graded)}",
        output=f"answer_len={len(answer)}, citations={len(citations)}",
    )

    return {
        "answer": answer,
        "citations": citations,
        "refused": False,
        "trace": state.get("trace", []) + [trace_step],
    }


async def refuse_node(state: RagState) -> dict:
    """Refuse to answer when retrieval fails."""
    trace_step = TraceStep(
        node="refuse",
        input=state["question"],
        output="refused - insufficient relevant information",
    )

    return {
        "answer": REFUSE_PROMPT,
        "citations": [],
        "refused": True,
        "trace": state.get("trace", []) + [trace_step],
    }


def _extract_citations(answer: str, graded_chunks: list[dict]) -> list[Citation]:
    """Extract citation markers from answer and map to graded chunks.
    Post-validate: only include citations that reference actual graded chunks.
    """
    citations: list[Citation] = []
    # Find all [n] markers in the answer
    markers = re.findall(r'\[(\d+)\]', answer)
    seen = set()

    for marker_num in markers:
        idx = int(marker_num) - 1  # 1-indexed to 0-indexed
        if idx < 0 or idx >= len(graded_chunks):
            continue
        if marker_num in seen:
            continue
        seen.add(marker_num)

        chunk = graded_chunks[idx]
        citations.append(Citation(
            marker=f"[{marker_num}]",
            source=chunk["source"],
            section=chunk["section"],
            chunk_id=chunk["chunk_id"],
            text=chunk["text"][:200],  # truncate for display
            source_url=chunk.get("source_url", ""),
            section_title=chunk.get("section_title", ""),
        ))

    return citations
