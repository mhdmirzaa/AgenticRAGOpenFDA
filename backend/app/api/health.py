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

    status["embed_dim"] = settings.embed_dim

    # Primary store: OpenSearch when configured, else the Chroma fallback.
    # Report a unified `chroma.documents` doc count (the frontend reads it) plus
    # a `store` block naming the active backend.
    doc_count = 0
    store_backend = "chroma"
    try:
        from app.retrieval.opensearch_store import get_opensearch_store
        os_store = get_opensearch_store()
        if os_store is not None:
            store_backend = "opensearch"
            doc_count = os_store.count()
            status["store"] = {
                "backend": "opensearch",
                "index": settings.opensearch_index,
                "documents": doc_count,
                "reachable": True,
            }
    except Exception as e:
        status["store"] = {"backend": "opensearch", "reachable": False, "error": str(e)}

    if store_backend == "chroma":
        try:
            vs = get_vectorstore()
            doc_count = vs.count()
            status["store"] = {"backend": "chroma", "documents": doc_count,
                               "reachable": True}
        except Exception as e:
            status["store"] = {"backend": "chroma", "reachable": False, "error": str(e)}
            status["status"] = "degraded"

    # Back-compat: the frontend + tests read `chroma.documents`.
    status["chroma"] = {"reachable": status.get("store", {}).get("reachable", False),
                        "documents": doc_count}

    # Cache stats + active backend (redis|memory) — performance visibility.
    try:
        from app.retrieval.cache import cache_stats, answer_cache_stats
        status["embedding_cache"] = cache_stats()
        status["cache_backend"] = status["embedding_cache"].get("backend")
        status["answer_cache"] = answer_cache_stats()
    except Exception:
        pass

    return status
