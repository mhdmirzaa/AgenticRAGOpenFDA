"""MaiStorage retrieval layer.

Lazy re-exports (PEP 562): importing this package must not eagerly pull in
chromadb (vectorstore) or sentence-transformers (reranker), so a read-only
consumer that only needs, say, `opensearch_store` stays light.
"""

__all__ = ["VectorStore", "get_vectorstore", "reset_vectorstore", "rerank"]


def __getattr__(name):
    if name in ("VectorStore", "get_vectorstore", "reset_vectorstore"):
        from app.retrieval import vectorstore as _vs
        return getattr(_vs, name)
    if name == "rerank":
        from app.retrieval.reranker import rerank
        return rerank
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
