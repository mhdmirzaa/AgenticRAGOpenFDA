"""
Pydantic request/response + trace schemas.  [M3 grows through M6]

Contracts (keep stable -- frontend lib/stream.ts depends on these):
  ChatRequest   { question: str }
  Citation      { marker, source, section, chunk_id, text }
  TraceStep     { node, input, output }
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator


def _validate_question(v: str) -> str:
    """Reject empty / oversized questions (security item 3, input validation).

    A hard character cap (config `max_question_chars`) blunts prompt-bloat DoS and
    keeps LLM cost bounded; the value is validated as data, never interpolated
    into SQL or a shell.
    """
    v = (v or "").strip()
    if not v:
        raise ValueError("question must not be empty")
    from app.config import get_settings
    cap = get_settings().max_question_chars
    if len(v) > cap:
        raise ValueError(f"question exceeds the {cap}-character limit")
    return v


def _validate_optional_id(v: str | None) -> str | None:
    """Bound the session_id length so a path/param can't smuggle a huge value."""
    if v is None:
        return None
    if len(v) > 128:
        raise ValueError("session_id too long")
    return v


class ChatRequest(BaseModel):
    """Incoming chat question."""
    question: str
    optimized: bool = True  # use hybrid+rerank retrieval (default on for the demo)
    session_id: str | None = None  # optional: persist + load conversation memory

    _v_q = field_validator("question")(_validate_question)
    _v_s = field_validator("session_id")(_validate_optional_id)


class AskRequest(BaseModel):
    """Non-streaming agentic request (course-parity /ask-agentic + Telegram)."""
    question: str
    session_id: str | None = None

    _v_q = field_validator("question")(_validate_question)
    _v_s = field_validator("session_id")(_validate_optional_id)


class Citation(BaseModel):
    """A single citation reference."""
    marker: str          # e.g. "[1]"
    source: str          # e.g. "ibuprofen" (drug name) or "handbook.md"
    section: str         # e.g. "warnings"
    chunk_id: str        # stable unique chunk identifier
    text: str            # the chunk text snippet
    source_url: str = "" # e.g. DailyMed label URL (FDA labels)
    section_title: str = ""  # human-readable section, e.g. "Warnings"


class AskResponse(BaseModel):
    """Non-streaming agentic answer."""
    answer: str
    citations: list[Citation]
    trace_id: str
    refused: bool = False
    blocked: bool = False


class TraceStep(BaseModel):
    """One step in the agent decision trace."""
    node: str            # e.g. "route", "retrieve", "grade"
    input: str           # what went into this node
    output: str          # what came out


class TraceRecord(BaseModel):
    """Complete agent trace for a request."""
    trace_id: str
    steps: list[TraceStep]


class ChatDoneEvent(BaseModel):
    """Final SSE event payload."""
    type: str = "done"
    citations: list[Citation]
    trace_id: str
    refused: bool = False
    blocked: bool = False


class ChatTokenEvent(BaseModel):
    """Streaming token SSE event."""
    type: str = "token"
    text: str


class ChatStageEvent(BaseModel):
    """Live agent-stage event for the evidence panel (additive, non-breaking).

    Emitted as the agent progresses so the UI can animate a stage timeline in
    real time. `stage` is one of: safety, route, scope, search, grade, decide,
    generate, refuse, blocked. `status` is "active" or "done". The `scope` stage
    reports the resolved drug scope for metadata-scoped retrieval (e.g.
    "Scope: doxycycline" or "Scope: all").
    """
    type: str = "stage"
    stage: str
    status: str = "done"
    detail: str = ""


class EvidenceChunk(BaseModel):
    """A retrieved candidate with its grade, for the evidence panel."""
    chunk_id: str
    source: str
    section: str
    section_title: str = ""
    text: str
    source_url: str = ""
    grade: str = "PASS"  # PASS | FAIL


class ChatEvidenceEvent(BaseModel):
    """The graded candidate set, emitted once after grading."""
    type: str = "evidence"
    chunks: list[EvidenceChunk]


class ChatErrorEvent(BaseModel):
    """Error SSE event."""
    type: str = "error"
    message: str
