"""
POST /ask-agentic -- [PRD v3.0 M4, course-parity endpoint].

Non-streaming agentic answer. Runs the identical guardrail -> route -> loop ->
generate/refuse pipeline as /chat, but returns a single JSON payload. Used by
the course-faithful endpoint name and by the Telegram bot (a thin client that
cannot consume SSE).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.agent.graph import run_agent_answer
from app.models import AskRequest, AskResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _load_memory(session_id: str | None) -> list[dict]:
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
    if not session_id:
        return
    try:
        from app.db import add_message
        add_message(session_id, role, content, citations=citations, trace_id=trace_id)
    except Exception as e:
        logger.warning("message persist skipped: %s", e)


@router.post("/ask-agentic", response_model=AskResponse)
async def ask_agentic(request: AskRequest) -> AskResponse:
    """Return a full agentic answer (non-streaming) with validated citations."""
    session_id = request.session_id
    history = _load_memory(session_id)
    _persist(session_id, "user", request.question)

    try:
        result = await run_agent_answer(request.question, history=history)
    except Exception as e:
        # Log the real error server-side; return a generic message (item 8).
        logger.exception("ask-agentic failed: %s", e)
        raise HTTPException(status_code=503, detail="The assistant is temporarily unavailable.")

    _persist(session_id, "assistant", result["answer"],
             citations=result["citations"], trace_id=result["trace_id"])

    from app.metrics import get_metrics
    get_metrics().record_outcome(refused=bool(result.get("refused")),
                                 blocked=bool(result.get("blocked")))

    return AskResponse(**result)
