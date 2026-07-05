"""
Hybrid retrieval (bonus).  [M7].
Dense (Chroma vector) + Keyword (BM25 via rank-bm25), merged with RRF.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from app.retrieval.vectorstore import RetrievedChunk, get_vectorstore


@dataclass
class HybridCandidate:
    """A candidate from hybrid retrieval with fused score."""
    chunk_id: str
    text: str
    source: str
    section: str
    dense_rank: int | None = None
    keyword_rank: int | None = None
    rrf_score: float = 0.0
    metadata: dict | None = None


class HybridRetriever:
    """Combines dense (vector) and keyword (BM25) retrieval using RRF."""

    def __init__(self) -> None:
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list[RetrievedChunk] = []

    def build_bm25_index(self, chunks: list) -> None:
        """Build BM25 index from chunk objects (call after ingestion)."""
        if not chunks:
            self._bm25 = None
            self._bm25_chunks = []
            return
        tokenized = [_tokenize(c.text) for c in chunks]
        self._bm25 = BM25Okapi(tokenized)
        self._bm25_chunks = chunks

    def ensure_index(self) -> None:
        """Lazily (re)build the BM25 index from whatever is in the vector store.

        Rebuilds when empty or when the corpus size changed (e.g. after re-ingest).
        """
        vs = get_vectorstore()
        current = vs.count()
        if self._bm25 is None or len(self._bm25_chunks) != current:
            self.build_bm25_index(vs.get_all_chunks())

    async def retrieve(
        self,
        query: str,
        top_k: int = 8,
        rrf_k: int = 60,
    ) -> list[HybridCandidate]:
        """Run hybrid retrieval: dense + BM25, merge with RRF."""
        # Dense retrieval (query embedding is cached across retries)
        from app.retrieval.cache import cached_embed
        query_embedding = await cached_embed(query)
        vs = get_vectorstore()
        dense_results = vs.query(query_embedding, n_results=top_k * 2)

        # BM25 keyword retrieval
        keyword_results = self._bm25_search(query, top_k * 2)

        # Reciprocal Rank Fusion
        return _reciprocal_rank_fusion(
            dense_results, keyword_results, top_k=top_k, k=rrf_k
        )

    def _bm25_search(self, query: str, top_n: int) -> list[RetrievedChunk]:
        """Search using BM25."""
        if self._bm25 is None or not self._bm25_chunks:
            return []

        tokenized_query = _tokenize(query)
        scores = self._bm25.get_scores(tokenized_query)

        scored_chunks = list(zip(scores, self._bm25_chunks))
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, chunk in scored_chunks[:top_n]:
            results.append(RetrievedChunk(
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                source=chunk.source,
                section=chunk.section,
                score=float(score),
                metadata=getattr(chunk, 'metadata', {}),
            ))
        return results


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    text = text.lower()
    tokens = re.findall(r'\b\w+\b', text)
    return tokens


def _reciprocal_rank_fusion(
    dense: list[RetrievedChunk],
    keyword: list[RetrievedChunk],
    top_k: int = 8,
    k: int = 60,
) -> list[HybridCandidate]:
    """Merge dense and keyword results using weighted Reciprocal Rank Fusion.

    Mirrors the OpenSearch store: dense (the stronger signal) is weighted above
    keyword, and the single strongest dense hit is anchored so fusion can never
    drop it below the returned top_k. Keeps the two backends behaviorally
    consistent (ENHANCE item 2).
    """
    from app.config import get_settings
    settings = get_settings()
    dense_w = settings.rrf_dense_weight
    kw_w = settings.rrf_bm25_weight

    candidates: dict[str, HybridCandidate] = {}

    # Process dense results
    for rank, chunk in enumerate(dense):
        cid = chunk.chunk_id
        if cid not in candidates:
            candidates[cid] = HybridCandidate(
                chunk_id=cid,
                text=chunk.text,
                source=chunk.source,
                section=chunk.section,
                metadata=chunk.metadata,
            )
        candidates[cid].dense_rank = rank + 1
        candidates[cid].rrf_score += dense_w / (k + rank + 1)

    # Process keyword results
    for rank, chunk in enumerate(keyword):
        cid = chunk.chunk_id
        if cid not in candidates:
            candidates[cid] = HybridCandidate(
                chunk_id=cid,
                text=chunk.text,
                source=chunk.source,
                section=chunk.section,
                metadata=chunk.metadata,
            )
        candidates[cid].keyword_rank = rank + 1
        candidates[cid].rrf_score += kw_w / (k + rank + 1)

    # Sort by fused score and return top_k.
    merged = sorted(candidates.values(), key=lambda c: c.rrf_score, reverse=True)
    top = merged[:top_k]

    # Dense-anchor guard: guarantee the strongest dense hit is in the pool.
    if dense:
        dense_top_id = dense[0].chunk_id
        if dense_top_id not in {c.chunk_id for c in top}:
            anchor = candidates.get(dense_top_id)
            if anchor is not None:
                if len(top) >= top_k and top:
                    top[-1] = anchor
                else:
                    top.append(anchor)
    return top


_hybrid_instance: HybridRetriever | None = None


def get_hybrid_retriever() -> HybridRetriever:
    """Singleton hybrid retriever."""
    global _hybrid_instance
    if _hybrid_instance is None:
        _hybrid_instance = HybridRetriever()
    return _hybrid_instance
