"""
Chat session endpoints.  [production item 2]

POST /sessions                 -> create a new chat session
GET  /sessions/{id}/messages   -> full message history for a session

Degrades gracefully if the database is unavailable.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.post("/sessions")
async def create_session():
    """Create a new chat session and return its id."""
    try:
        from app.db import create_session as _create
        return {"session_id": _create()}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Persistence unavailable: {e}")


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Return all messages for a session (empty list if unknown)."""
    try:
        from app.db import get_messages
        return {"session_id": session_id, "messages": get_messages(session_id)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Persistence unavailable: {e}")
