"""
POST /chat -- [M3 single-pass; M6 agentic].
Streams the answer token-by-token over SSE, then a final done event
with citations + trace_id. Honor the event contract in models.py.
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models import ChatRequest
from app.agent.graph import run_agent_streaming

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_memory(session_id: str | None) -> list[dict]:
    """Last-N prior messages for this session (empty if none / DB down)."""
    if not session_id:
        return []
    try:
        from app.db import get_recent_messages
        return get_recent_messages(session_id)
    except Exception as e:
        logger.warning("memory load skipped: %s", e)
        return []


def _persist(session_id: str | None, role: str, content: str,
             citations=None, trace_id=None) -> None:
    """Persist a message; never let a persistence failure break the chat."""
    if not session_id:
        return
    try:
        from app.db import add_message
        add_message(session_id, role, content, citations=citations, trace_id=trace_id)
    except Exception as e:
        logger.warning("message persist skipped: %s", e)


@router.post("/chat")
async def chat(request: ChatRequest):
    """Stream an agentic RAG answer over SSE (with optional session memory)."""

    session_id = request.session_id
    history = _load_memory(session_id)
    _persist(session_id, "user", request.question)

    async def event_stream():
        answer_parts: list[str] = []
        citations: list = []
        trace_id: str | None = None

        async for event in run_agent_streaming(
            request.question, use_hybrid=request.optimized, history=history
        ):
            if event.get("type") == "token":
                answer_parts.append(event.get("text", ""))
            elif event.get("type") == "done":
                citations = event.get("citations", [])
                trace_id = event.get("trace_id")
            data = json.dumps(event, default=str)
            yield f"data: {data}\n\n"

        _persist(session_id, "assistant", "".join(answer_parts),
                 citations=citations, trace_id=trace_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
