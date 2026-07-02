"""
Local cross-encoder reranker (bonus).  [M7].
Uses sentence-transformers cross-encoder for reranking.
Falls back to passthrough if model unavailable.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_reranker_model = None
_reranker_available = None


def _load_reranker():
    """Lazy-load the cross-encoder reranker model."""
    global _reranker_model, _reranker_available
    if _reranker_available is not None:
        return _reranker_available

    import os
    if os.environ.get("DISABLE_RERANKER") == "1":
        logger.info("Reranker disabled via DISABLE_RERANKER=1; using passthrough")
        _reranker_available = False
        return False

    try:
        from sentence_transformers import CrossEncoder
        _reranker_model = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
        _reranker_available = True
        logger.info("Cross-encoder reranker loaded successfully")
    except Exception as e:
        logger.warning(f"Reranker not available, falling back to passthrough: {e}")
        _reranker_available = False

    return _reranker_available


def rerank(query: str, candidates: list, top_n: int = 4) -> list:
    """Rerank candidates using cross-encoder.

    Args:
        query: The search query
        candidates: List of HybridCandidate or RetrievedChunk objects
        top_n: Number of top results to keep

    Returns:
        Reranked and truncated list of candidates
    """
    if not candidates:
        return []

    if not _load_reranker() or _reranker_model is None:
        # Fallback: return top_n by existing score
        return candidates[:top_n]

    # Build query-document pairs
    pairs = [(query, c.text) for c in candidates]

    # Score with cross-encoder
    scores = _reranker_model.predict(pairs)

    # Attach scores and sort
    scored = list(zip(scores, candidates))
    scored.sort(key=lambda x: float(x[0]), reverse=True)

    return [c for _, c in scored[:top_n]]
