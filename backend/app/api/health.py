"""GET /health -- [M1]. Report Chroma reachable + provider/models ready."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings
from app.retrieval.vectorstore import get_vectorstore

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint reporting system status."""
    settings = get_settings()
    status = {
        "status": "healthy",
        "provider": settings.llm_provider,
        "gen_model": settings.gen_model,
        "embed_model": settings.embed_model,
    }

    # Check Chroma
    try:
        vs = get_vectorstore()
        doc_count = vs.count()
        status["chroma"] = {"reachable": True, "documents": doc_count}
    except Exception as e:
        status["chroma"] = {"reachable": False, "error": str(e)}
        status["status"] = "degraded"

    # Cache stats + active backend (redis|memory) — performance visibility.
    try:
        from app.retrieval.cache import cache_stats
        status["embedding_cache"] = cache_stats()
        status["cache_backend"] = status["embedding_cache"].get("backend")
    except Exception:
        pass

    return status
