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
    GUARDRAIL_PROMPT,
    GUARDRAIL_REFUSE_CARING,
    GUARDRAIL_REFUSE_NEUTRAL,
    GUARDRAIL_REFUSE_ADVICE,
    GENERATION_UNAVAILABLE_MESSAGE,
)
from app.config import get_settings
from app.models import Citation, TraceStep
from app.providers.base import get_provider
from app.retrieval.vectorstore import get_vectorstore


# Keyword fast-path for the safety guardrail: obvious, deterministic, free.
# Maps a matched phrase to a block category. Legitimate dosing questions ("max
# safe dose") are intentionally NOT here — they fall through to SAFE / the LLM.
_SELFHARM_PATTERNS = [
    "kill myself", "suicide", "suicidal", "end my life", "overdose to die",
    "how much to die", "lethal dose", "fatal dose", "how much would kill",
    "enough to die", "want to die", "how to overdose", "od on",
    "take my own life", "end it all", "poison myself", "harm myself",
    "hurt myself", "how many pills to die", "kill me",
]
_MISUSE_PATTERNS = [
    "get high", "getting high", "to get high on", "abuse", "recreational",
    "snort", "inject to", "ignore your instructions", "ignore previous",
    "disregard your", "how to poison", "harm someone", "hurt someone",
    "shoot up", "get someone high", "spike someone", "how to get addicted",
]

_BLOCK_MESSAGES = {
    "SELFHARM": GUARDRAIL_REFUSE_CARING,
    "MISUSE": GUARDRAIL_REFUSE_NEUTRAL,
    "ADVICE": GUARDRAIL_REFUSE_ADVICE,
}


def _keyword_guardrail(question: str) -> str | None:
    """Deterministic fast-path. Returns a block category or None (undecided)."""
    q = question.lower()
    for p in _SELFHARM_PATTERNS:
        if p in q:
            return "SELFHARM"
    for p in _MISUSE_PATTERNS:
        if p in q:
            return "MISUSE"
    return None


async def guardrail_node(state: RagState) -> dict:
    """First node: decide whether the question may be answered at all.

    Hybrid decision: a keyword fast-path handles obvious unsafe cases instantly
    and for free; anything it can't settle goes to one small gpt-4.1-mini intent
    check. If the LLM call fails, we degrade to the keyword verdict (SAFE if the
    fast-path also found nothing) so the guardrail never breaks a request.
    """
    settings = get_settings()
    question = state["question"]

    if not settings.enable_guardrail:
        return {"blocked": False, "trace_id": state.get("trace_id", str(uuid.uuid4()))}

    category = _keyword_guardrail(question)
    decided_by = "keyword"

    if category is None:
        # Subtle / paraphrased cases -> one small LLM intent check.
        try:
            provider = get_provider()
            resp = await provider.complete(GUARDRAIL_PROMPT.format(question=question))
            verdict = resp.strip().upper()
            decided_by = "llm"
            if "SELFHARM" in verdict:
                category = "SELFHARM"
            elif "MISUSE" in verdict:
                category = "MISUSE"
            elif "ADVICE" in verdict:
                category = "ADVICE"
            else:
                category = None  # SAFE
        except Exception:
            category = None  # degrade to keyword verdict (SAFE here)
            decided_by = "keyword(llm-failed)"

    blocked = category is not None
    trace_step = TraceStep(
        node="guardrail",
        input=question,
        output=(f"blocked={blocked} category={category or 'SAFE'} "
                f"(via {decided_by})"),
    )

    return {
        "blocked": blocked,
        "block_category": category or "",
        "block_message": _BLOCK_MESSAGES.get(category or "", ""),
        "trace": state.get("trace", []) + [trace_step],
        "trace_id": state.get("trace_id", str(uuid.uuid4())),
        "iterations": 0,
    }


async def route_node(state: RagState) -> dict:
    """Decide if the question needs retrieval or should be refused."""
    provider = get_provider()
    question = state["question"]

    prompt = ROUTE_PROMPT.format(question=question)
    try:
        response = await provider.complete(prompt)
        decision = response.strip().upper()
        needs_retrieval = "RETRIEVE" in decision
    except Exception as e:
        # LLM timeout/outage on the router must not 500 the request: default to
        # attempting retrieval (the safe degrade — the loop can still refuse).
        decision = f"error: {e} -> defaulting to RETRIEVE"
        needs_retrieval = True

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
    try:
        rewritten = await provider.complete(prompt)
        rewritten = rewritten.strip().strip('"').strip("'")
    except Exception:
        # A rewrite failure must not break retrieval: fall back to the previous
        # query, or the raw question on the first pass.
        rewritten = previous_query or question
    if not rewritten:
        rewritten = previous_query or question

    trace_step = TraceStep(
        node="rewrite",
        input=f"question={question}, prev_query={previous_query}, iter={iteration}",
        output=rewritten,
    )

    return {
        "query": rewritten,
        "trace": state.get("trace", []) + [trace_step],
    }


async def _retrieve_candidates(query: str, use_hybrid: bool,
                               drug_filter: set[str] | None) -> list[dict]:
    """Run one retrieval pass (dense or hybrid), optionally scoped to drugs.

    `drug_filter` (normalized drug_keys) restricts the candidate set BEFORE the
    similarity search — the metadata-scoping fix for cross-drug dilution. None
    means the unscoped path (unchanged behavior).
    """
    settings = get_settings()
    out: list[dict] = []

    # Primary store: OpenSearch (BM25 + kNN, native hybrid RRF) when active.
    from app.retrieval.opensearch_store import get_opensearch_store
    store = get_opensearch_store()
    if store is not None:
        from app.retrieval.cache import cached_embed
        query_embedding = await cached_embed(query)
        if use_hybrid:
            return store.hybrid_search(query, query_embedding,
                                       top_k=settings.top_k, drug_filter=drug_filter)
        return store.dense_search(query_embedding, top_k=settings.top_k,
                                  drug_filter=drug_filter)

    # Fallback store: embedded Chroma + rank-bm25.
    if use_hybrid:
        from app.retrieval.hybrid import get_hybrid_retriever
        retriever = get_hybrid_retriever()
        retriever.ensure_index()
        merged = await retriever.retrieve(query, top_k=settings.top_k)
        for r in merged:
            meta = r.metadata or {}
            # rank-bm25 has no native metadata filter; post-filter the merged
            # results by drug_key so the scoped path still narrows to the drug.
            if drug_filter and (meta.get("drug_key") or "") not in drug_filter:
                continue
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
        results = vs.query(query_embedding, n_results=settings.top_k,
                           drug_filter=drug_filter)
        for r in results:
            meta = r.metadata or {}
            out.append({
                "chunk_id": r.chunk_id, "text": r.text, "source": r.source,
                "section": r.section, "score": r.score,
                "source_url": meta.get("source_url", ""),
                "section_title": meta.get("section_title", ""),
            })
    return out


async def _resolve_scope_for_state(state: RagState):
    """Resolve (once per turn) which drug(s) the question is about.

    Returns a Scope. Reuses a scope already stashed in state (so re-retrieval
    loops don't re-run entity resolution). Off (or any failure) -> NONE scope.
    """
    from app.retrieval.scoping import Scope, get_drug_catalog, resolve_scope_cached

    cached = state.get("scope")
    if cached:
        return Scope.from_dict(cached)

    settings = get_settings()
    if not state.get("use_scoping", settings.enable_scoping):
        return Scope()
    try:
        catalog = get_drug_catalog()
        return await resolve_scope_cached(state["question"], catalog)
    except Exception:  # noqa: BLE001 - resolution never breaks retrieval
        return Scope()


async def retrieve_node(state: RagState) -> dict:
    """Retrieve candidates from the vector store, drug-scoped when possible.

    Optimized mode (use_hybrid) merges dense + BM25 via RRF; baseline mode does
    dense-only similarity search. Query embeddings are cached across retries.

    Metadata scoping (scoped-retrieval): if the question resolves to a drug set
    (NAMED / CONDITION), the candidate set is restricted to those drugs BEFORE
    similarity search — removing the wrong-drug hard negatives that dilute a
    homogeneous corpus. Safety fallback: a scoped search returning fewer than
    `scope_min_results` auto-retries UNFILTERED, so recall is never worse than
    today. The path that ran (scoped | unfiltered) is recorded in the trace.
    """
    settings = get_settings()
    query = state.get("query", state["question"])
    use_hybrid = state.get("use_hybrid", False)
    base_mode = "hybrid(dense+BM25)" if use_hybrid else "dense"

    scope = await _resolve_scope_for_state(state)
    drug_filter = scope.drug_keys if scope.is_filtered else None

    # Retrieval-results cache (item 7): key includes the scope so a scoped and an
    # unscoped run of the same query never collide.
    from app.retrieval.cache import cached_retrieval
    scope_key = "+".join(sorted(scope.drug_keys)) if scope.is_filtered else "all"

    retrieval_error = None
    scope_path = "unfiltered"
    try:
        if drug_filter:
            candidates = await cached_retrieval(
                query, f"{base_mode}|scope:{scope_key}",
                lambda: _retrieve_candidates(query, use_hybrid, drug_filter),
            )
            scope_path = "scoped"
            # Safety fallback: too few scoped hits -> retry UNFILTERED so a
            # sparsely-indexed drug can never starve the answer.
            if len(candidates) < settings.scope_min_results:
                candidates = await cached_retrieval(
                    query, base_mode,
                    lambda: _retrieve_candidates(query, use_hybrid, None),
                )
                scope_path = "unfiltered(scoped-too-few)"
        else:
            candidates = await cached_retrieval(
                query, base_mode,
                lambda: _retrieve_candidates(query, use_hybrid, None),
            )
    except Exception as e:  # noqa: BLE001 - degrade to empty, never crash
        candidates = []
        retrieval_error = e

    output = (f"found {len(candidates)} candidates via {scope_path} "
              f"(scope: {scope.display}): {[c['chunk_id'] for c in candidates]}") \
        if retrieval_error is None \
        else f"retrieval unavailable ({retrieval_error}); degraded to 0 candidates"
    trace_step = TraceStep(
        node="retrieve",
        input=f"query={query}, top_k={settings.top_k}, mode={base_mode}, "
              f"scope={scope.kind}",
        output=output,
    )

    return {
        "candidates": candidates,
        "scope": scope.to_dict(),
        "scope_path": scope_path,
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
    """Grade candidate chunks for relevance.

    Performance (v3.2): grade ALL reranked candidates in a SINGLE batched LLM
    call (one prompt -> a JSON verdict list) instead of one call per candidate.
    The drug-aware grading logic is identical — only the call pattern changes.
    If the batch response can't be parsed (or the batch call errors), we degrade
    to the original one-call-per-chunk path, so a flaky batch never breaks a turn.

    `grade_top_n` (config, 0 = all) optionally caps how many of the reranked
    candidates are graded — a latency/token lever that composes with batching.
    """
    settings = get_settings()
    question = state["question"]
    candidates = state.get("candidates", [])
    if settings.grade_top_n and settings.grade_top_n > 0:
        candidates = candidates[:settings.grade_top_n]

    if not candidates:
        trace_step = TraceStep(
            node="grade",
            input=f"grading 0 chunks for: {question}",
            output="passed: 0/0 (no candidates)",
        )
        return {"graded": [], "trace": state.get("trace", []) + [trace_step]}

    graded, grade_details, how = await _grade_batch(question, candidates)
    if graded is None:  # batch unusable -> degrade to per-chunk grading
        graded, grade_details, how = await _grade_per_chunk(question, candidates)

    trace_step = TraceStep(
        node="grade",
        input=f"grading {len(candidates)} chunks for: {question} (via {how})",
        output=f"passed: {len(graded)}/{len(candidates)} | {', '.join(grade_details)}",
    )

    return {
        "graded": graded,
        "trace": state.get("trace", []) + [trace_step],
    }


async def _grade_batch(question: str, candidates: list[dict]):
    """One LLM call grading every candidate. Returns (graded, details, "batch")
    on success, or (None, None, None) if the response can't be trusted (caller
    then falls back to per-chunk grading)."""
    from app.agent.prompts import GRADE_BATCH_PROMPT

    provider = get_provider()
    # Tag each chunk with its source drug so the grader can apply the drug-match
    # rule reliably (a wrong-drug chunk that shares the asked section — e.g. some
    # other drug's `warnings` for a drug not in the corpus — is then rejected).
    chunks_block = "\n\n".join(
        f"[{i}] (drug: {c.get('source', '?')}) {c['text'][:1500]}"
        for i, c in enumerate(candidates, 1)
    )
    prompt = GRADE_BATCH_PROMPT.format(question=question, chunks=chunks_block)
    try:
        response = await provider.complete(prompt)
    except Exception:
        return None, None, None

    verdicts = _parse_batch_verdicts(response, len(candidates))
    if verdicts is None:
        return None, None, None

    graded, details = [], []
    for i, chunk in enumerate(candidates, 1):
        is_relevant = verdicts.get(i, False)
        details.append(f"{chunk['chunk_id']}={'YES' if is_relevant else 'NO'}")
        if is_relevant:
            graded.append(chunk)
    return graded, details, "batch"


def _parse_batch_verdicts(response: str, n: int) -> dict | None:
    """Parse a batch grader reply into {index: bool}. Returns None (=> caller
    falls back) if the reply is not a usable verdict list covering all n chunks."""
    import json as _json

    if not response or not response.strip():
        return None
    text = response.strip()
    # Extract the JSON array even if the model wrapped it in prose/code fences.
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        arr = _json.loads(text[start:end + 1])
    except Exception:
        return None
    if not isinstance(arr, list) or len(arr) != n:
        return None

    verdicts: dict[int, bool] = {}
    for item in arr:
        if not isinstance(item, dict) or "index" not in item or "relevant" not in item:
            return None
        try:
            idx = int(item["index"])
        except (TypeError, ValueError):
            return None
        verdicts[idx] = "YES" in str(item["relevant"]).strip().upper()
    # Every chunk 1..n must have a verdict (no silent drops).
    if set(verdicts) != set(range(1, n + 1)):
        return None
    return verdicts


async def _grade_per_chunk(question: str, candidates: list[dict]):
    """Fallback: original one-LLM-call-per-candidate grading. Fails a chunk
    CLOSED on a grader error (we never generate from unverified evidence)."""
    provider = get_provider()
    graded, details = [], []
    for chunk in candidates:
        prompt = GRADE_PROMPT.format(question=question, chunk_text=chunk["text"][:1500])
        try:
            response = await provider.complete(prompt)
            is_relevant = "YES" in response.strip().upper()
            label = "YES" if is_relevant else "NO"
        except Exception:
            is_relevant = False
            label = "ERR"
        details.append(f"{chunk['chunk_id']}={label}")
        if is_relevant:
            graded.append(chunk)
    return graded, details, "per-chunk"


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
    try:
        answer = await provider.complete(prompt)
    except Exception as e:
        # Generation LLM outage: degrade to a clean, disclaimer-bearing decline
        # (refused=True) instead of surfacing a raw 500 to the user.
        trace_step = TraceStep(
            node="generate",
            input=f"question={question}, chunks={len(graded)}",
            output=f"generation failed ({e}) -> graceful refusal",
        )
        return {
            "answer": GENERATION_UNAVAILABLE_MESSAGE,
            "citations": [],
            "refused": True,
            "trace": state.get("trace", []) + [trace_step],
        }

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
    """Refuse to answer.

    Two distinct refusal moments share this node:
      - guardrail block (unsafe/off-limits) -> a tone-appropriate safety message
        (caring for self-harm, neutral for misuse/advice), traced as "blocked".
      - unanswerable (route said off-domain, or the graded set stayed empty) ->
        the standard "not in my FDA labels" refusal.
    """
    if state.get("blocked"):
        answer = state.get("block_message") or REFUSE_PROMPT
        trace_step = TraceStep(
            node="refuse",
            input=state["question"],
            output=f"blocked by guardrail: {state.get('block_category', '')}",
        )
    else:
        answer = REFUSE_PROMPT
        trace_step = TraceStep(
            node="refuse",
            input=state["question"],
            output="refused - insufficient relevant information",
        )

    return {
        "answer": answer,
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
