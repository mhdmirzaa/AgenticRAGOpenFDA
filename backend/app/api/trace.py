"""GET /trace/{id} -- [M6; hardened in security-hardening].

Returns the recorded agent decision trace, bound to the caller who produced it.
trace_id is an unguessable uuid4; a strict id shape is required before lookup;
when AUTH_ENABLED, only the trace's owner may read it. Malformed / unknown /
non-owned all return 404 (no enumeration leak). Item 2.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models import TraceRecord, TraceStep
from app.security import current_caller, is_valid_id

router = APIRouter()

# In-memory trace store (production would use a database). Each entry keeps the
# owner (caller id) alongside the steps so reads can be access-controlled.
_trace_store: dict[str, list[TraceStep]] = {}
_trace_owner: dict[str, str] = {}

_NOT_FOUND = HTTPException(status_code=404, detail="Not found.")


def store_trace(trace_id: str, steps: list[TraceStep], owner: str = "anon") -> None:
    """Store a trace (with its owner) for later retrieval."""
    _trace_store[trace_id] = steps
    _trace_owner[trace_id] = owner or "anon"


def get_trace(trace_id: str) -> list[TraceStep] | None:
    """Retrieve a stored trace's steps (no access control — internal use)."""
    return _trace_store.get(trace_id)


@router.get("/trace/{trace_id}")
async def get_trace_endpoint(trace_id: str):
    """Return the caller's own decision trace (404 for anything else)."""
    if not is_valid_id(trace_id):
        raise _NOT_FOUND
    steps = _trace_store.get(trace_id)
    if steps is None:
        raise _NOT_FOUND
    if get_settings().auth_enabled:
        owner = _trace_owner.get(trace_id, "anon")
        if owner not in ("anon", current_caller.get()):
            raise _NOT_FOUND
    return TraceRecord(trace_id=trace_id, steps=steps)
