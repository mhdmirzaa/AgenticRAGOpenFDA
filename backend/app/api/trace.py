"""GET /trace/{id} -- [M6]. Return the recorded agent decision trace."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models import TraceRecord, TraceStep

router = APIRouter()

# In-memory trace store (production would use a database)
_trace_store: dict[str, list[TraceStep]] = {}


def store_trace(trace_id: str, steps: list[TraceStep]) -> None:
    """Store a trace for later retrieval."""
    _trace_store[trace_id] = steps


def get_trace(trace_id: str) -> list[TraceStep] | None:
    """Retrieve a stored trace."""
    return _trace_store.get(trace_id)


@router.get("/trace/{trace_id}")
async def get_trace_endpoint(trace_id: str):
    """Return the recorded agent decision trace."""
    steps = get_trace(trace_id)
    if steps is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    
    return TraceRecord(trace_id=trace_id, steps=steps)
