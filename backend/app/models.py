"""
Pydantic request/response + trace schemas.  [M3 grows through M6]

Contracts (keep stable -- frontend lib/stream.ts depends on these):
  ChatRequest   { question: str }
  Citation      { marker, source, section, chunk_id, text }
  TraceStep     { node, input, output }
"""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """Incoming chat question."""
    question: str
    optimized: bool = True  # use hybrid+rerank retrieval (default on for the demo)
    session_id: str | None = None  # optional: persist + load conversation memory


class AskRequest(BaseModel):
    """Non-streaming agentic request (course-parity /ask-agentic + Telegram)."""
    question: str
    session_id: str | None = None


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
    real time. `stage` is one of: safety, route, search, grade, decide,
    generate, refuse, blocked. `status` is "active" or "done".
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
