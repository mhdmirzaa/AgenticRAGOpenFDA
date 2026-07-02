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


class Citation(BaseModel):
    """A single citation reference."""
    marker: str          # e.g. "[1]"
    source: str          # e.g. "handbook.md"
    section: str         # e.g. "leave-policy"
    chunk_id: str        # stable unique chunk identifier
    text: str            # the chunk text snippet


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


class ChatTokenEvent(BaseModel):
    """Streaming token SSE event."""
    type: str = "token"
    text: str


class ChatErrorEvent(BaseModel):
    """Error SSE event."""
    type: str = "error"
    message: str
