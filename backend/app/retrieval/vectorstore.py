"""Chroma client wrapper.  [M2]. get_or_create_collection, add, query. PersistentClient."""

from __future__ import annotations

from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import get_settings

COLLECTION_NAME = "maistorage_docs"


@dataclass
class RetrievedChunk:
    """A chunk retrieved from the vector store."""
    chunk_id: str
    text: str
    source: str
    section: str
    score: float  # similarity score (lower distance = better)
    metadata: dict = field(default_factory=dict)


class VectorStore:
    """Wrapper around ChromaDB for document storage and retrieval."""

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(
            path=settings.chroma_path,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def collection(self):
        return self._collection

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Upsert documents with embeddings into the collection."""
        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(
        self,
        query_embedding: list[float],
        n_results: int = 8,
        drug_filter: set[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Query the collection by embedding vector.

        `drug_filter` (a set of normalized drug_keys) scopes the search to those
        drugs via a metadata `where` clause — the Chroma-fallback equivalent of
        the OpenSearch drug filter (metadata-scoped retrieval).
        """
        where = None
        if drug_filter:
            keys = sorted(drug_filter)
            where = {"drug_key": keys[0]} if len(keys) == 1 else {"drug_key": {"$in": keys}}
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
            **({"where": where} if where else {}),
        )

        chunks: list[RetrievedChunk] = []
        if not results["ids"] or not results["ids"][0]:
            return chunks

        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            chunks.append(RetrievedChunk(
                chunk_id=chunk_id,
                text=results["documents"][0][i] if results["documents"] else "",
                source=meta.get("source", ""),
                section=meta.get("section", ""),
                score=1.0 - (results["distances"][0][i] if results["distances"] else 0),
                metadata=meta,
            ))

        return chunks

    def query_by_text(
        self,
        query_text: str,
        n_results: int = 8,
    ) -> list[RetrievedChunk]:
        """Query using Chroma's built-in embedding (fallback)."""
        results = self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        chunks: list[RetrievedChunk] = []
        if not results["ids"] or not results["ids"][0]:
            return chunks

        for i, chunk_id in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            chunks.append(RetrievedChunk(
                chunk_id=chunk_id,
                text=results["documents"][0][i] if results["documents"] else "",
                source=meta.get("source", ""),
                section=meta.get("section", ""),
                score=1.0 - (results["distances"][0][i] if results["distances"] else 0),
                metadata=meta,
            ))

        return chunks

    def get_all_chunks(self) -> list[RetrievedChunk]:
        """Return every stored chunk (used to build the BM25 keyword index)."""
        results = self._collection.get(include=["documents", "metadatas"])
        chunks: list[RetrievedChunk] = []
        ids = results.get("ids") or []
        for i, chunk_id in enumerate(ids):
            docs = results.get("documents") or []
            metas = results.get("metadatas") or []
            meta = metas[i] if i < len(metas) and metas[i] else {}
            chunks.append(RetrievedChunk(
                chunk_id=chunk_id,
                text=docs[i] if i < len(docs) else "",
                source=meta.get("source", ""),
                section=meta.get("section", ""),
                score=0.0,
                metadata=meta,
            ))
        return chunks

    def count(self) -> int:
        """Return total number of documents in collection."""
        return self._collection.count()

    def reset(self) -> None:
        """Delete and recreate the collection."""
        self._client.delete_collection(COLLECTION_NAME)
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )


_vs_instance: VectorStore | None = None


def get_vectorstore() -> VectorStore:
    """Singleton vectorstore instance."""
    global _vs_instance
    if _vs_instance is None:
        _vs_instance = VectorStore()
    return _vs_instance


def reset_vectorstore() -> None:
    """Reset vectorstore singleton (for testing)."""
    global _vs_instance
    _vs_instance = None
