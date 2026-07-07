"""
RagState TypedDict.  [M6]  rag-agentic Step 3.
Defines the state that flows through the LangGraph agent.
"""

from __future__ import annotations

from typing import TypedDict

from app.models import Citation, TraceStep


class RagState(TypedDict, total=False):
    """State flowing through the agentic RAG graph."""
    question: str                    # original user question
    query: str                       # rewritten search query
    candidates: list[dict]           # retrieved chunks (as dicts)
    graded: list[dict]               # chunks that passed grading
    iterations: int                  # current loop count
    answer: str                      # generated answer text
    citations: list[Citation]        # extracted citations
    trace: list[TraceStep]           # decision trace
    trace_id: str                    # unique trace identifier
    needs_retrieval: bool            # route decision
    is_sufficient: bool              # grade decision
    refused: bool                    # whether agent refused to answer
    use_hybrid: bool                 # optimized mode: dense+BM25 hybrid retrieval + rerank
    use_scoping: bool                # metadata-scoped retrieval on/off (eval lever)
    scope: dict                      # resolved drug scope {kind, drug_keys, display}
    scope_path: str                  # which retrieval path ran: scoped | unfiltered
    blocked: bool                    # guardrail blocked the question (safety)
    block_category: str              # SELFHARM | MISUSE | ADVICE (when blocked)
    block_message: str               # the tone-appropriate refusal text
