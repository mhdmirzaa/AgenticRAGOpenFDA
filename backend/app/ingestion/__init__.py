"""
MaiStorage ingestion pipeline.

Submodules
----------
loader   -- Load corpus files (.md, .txt) from the corpus/ directory.
chunker  -- Structure-aware markdown chunking (~512 tokens, ~64 overlap).
indexer  -- Embed chunks via the configured LLM provider and upsert to Chroma.
"""

from app.ingestion.loader import load_corpus
from app.ingestion.chunker import chunk_documents
from app.ingestion.indexer import index_chunks

__all__ = ["load_corpus", "chunk_documents", "index_chunks"]
