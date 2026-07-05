"""Embed chunks via get_provider().embed and upsert to Chroma with metadata.  [M2]  persist to disk."""

from __future__ import annotations

from app.providers.base import get_provider
from app.retrieval.vectorstore import get_vectorstore


async def index_chunks(chunks: list) -> int:
    """Embed all chunks and upsert to Chroma.

    Returns the number of chunks indexed.
    """
    if not chunks:
        return 0

    provider = get_provider()
    vs = get_vectorstore()

    # Batch embed for efficiency
    batch_size = 20
    all_ids: list[str] = []
    all_embeddings: list[list[float]] = []
    all_documents: list[str] = []
    all_metadatas: list[dict] = []

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c.text for c in batch]

        embeddings = await provider.embed_batch(texts)

        for chunk, embedding in zip(batch, embeddings):
            all_ids.append(chunk.chunk_id)
            all_embeddings.append(embedding)
            all_documents.append(chunk.text)
            meta = {
                "source": chunk.source,
                "section": chunk.section,
                "chunk_id": chunk.chunk_id,
            }
            # Carry through optional source metadata (FDA labels: label_id,
            # source_url, drug_name, brand_name) so citations can link out.
            for key in ("label_id", "source_url", "drug_name",
                        "brand_name", "section_title"):
                val = chunk.metadata.get(key)
                if val is not None and val != "":
                    meta[key] = val
            all_metadatas.append(meta)

    # Primary store: OpenSearch when configured (course parity); otherwise the
    # embedded Chroma fallback. Both take the same (ids, embeddings, docs, meta).
    from app.retrieval.opensearch_store import get_opensearch_store
    store = get_opensearch_store()
    if store is not None:
        store.add(
            ids=all_ids,
            embeddings=all_embeddings,
            documents=all_documents,
            metadatas=all_metadatas,
        )
    else:
        vs.add(
            ids=all_ids,
            embeddings=all_embeddings,
            documents=all_documents,
            metadatas=all_metadatas,
        )

    return len(all_ids)
