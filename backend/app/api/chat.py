"""
POST /chat -- [M3 single-pass; M6 agentic].
Streams the answer token-by-token over SSE, then a final done event
with citations + trace_id. Honor the event contract in models.py.
"""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.models import ChatRequest
from app.agent.graph import run_agent_streaming

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    """Stream an agentic RAG answer over SSE."""

    async def event_stream():
        async for event in run_agent_streaming(
            request.question, use_hybrid=request.optimized
        ):
            data = json.dumps(event, default=str)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
