"""
MaiStorage ingestion pipeline.

Submodules
----------
loader   -- Load corpus files (.md, .txt) from the corpus/ directory.
chunker  -- Structure-aware markdown chunking (~512 tokens, ~64 overlap).
indexer  -- Embed chunks via the configured LLM provider and upsert to Chroma.
"""

__all__ = ["load_corpus", "chunk_documents", "index_chunks"]


def __getattr__(name):
    """Lazy re-exports (PEP 562).

    Importing this package (or any submodule, e.g. `app.ingestion.openfda`) must
    NOT eagerly pull in the indexer -> vectorstore -> chromadb chain. The
    read-only Airflow worker imports only `openfda`/`loader` and should never
    need a vector-store driver. Heavy submodules load on first attribute access.
    """
    if name == "load_corpus":
        from app.ingestion.loader import load_corpus
        return load_corpus
    if name == "chunk_documents":
        from app.ingestion.chunker import chunk_documents
        return chunk_documents
    if name == "index_chunks":
        from app.ingestion.indexer import index_chunks
        return index_chunks
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
