"""
Chat session endpoints.  [production item 2; hardened in security-hardening]

POST /sessions                 -> create a new chat session (bound to the caller)
GET  /sessions/{id}/messages   -> message history, only for the session's owner

Access control (security item 2): session ids are unguessable uuid4; a strict id
shape is required before any lookup; when AUTH_ENABLED, a caller can only read a
session they own. Non-owned / malformed / unknown ids all return 404 (never 403)
so an attacker can't distinguish "exists but not yours" from "doesn't exist".
Degrades gracefully if the database is unavailable.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.security import current_caller, is_valid_id

router = APIRouter()

_NOT_FOUND = HTTPException(status_code=404, detail="Not found.")


@router.post("/sessions")
async def create_session():
    """Create a new chat session (owned by the caller) and return its id."""
    try:
        from app.db import create_session as _create
        return {"session_id": _create(owner=current_caller.get())}
    except Exception:
        # No internal detail in the response (security item 8).
        raise HTTPException(status_code=503, detail="Persistence unavailable.")


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Return the caller's own session messages (404 for anything else)."""
    if not is_valid_id(session_id):
        raise _NOT_FOUND
    try:
        from app.db import get_messages, get_session_owner
        if get_settings().auth_enabled:
            owner = get_session_owner(session_id)
            caller = current_caller.get()
            # Unknown, or owned by someone else -> indistinguishable 404.
            if owner is None or owner not in ("anon", caller):
                raise _NOT_FOUND
        return {"session_id": session_id, "messages": get_messages(session_id)}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Persistence unavailable.")
