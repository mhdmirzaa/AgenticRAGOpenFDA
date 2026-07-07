"""
POST /ingest       -- [M2]. (Re)build the Chroma index from corpus/.
POST /ingest/fda   -- [production item 1]. Fetch openFDA drug labels and
                      ADD them to the accumulating index (dedupe by label_id).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from app.ingestion.loader import load_corpus
from app.ingestion.chunker import chunk_documents
from app.ingestion.indexer import index_chunks
from app.ingestion.openfda import run_fda_ingestion, run_fda_growth
from app.retrieval.vectorstore import get_vectorstore

router = APIRouter()


class FdaIngestRequest(BaseModel):
    """Optional overrides for openFDA ingestion (defaults to the seed list)."""
    drugs: list[str] | None = None
    limit: int = 1


@router.post("/ingest")
async def ingest_corpus():
    """Load corpus, chunk, embed, and index into Chroma."""
    try:
        # Reset existing collection
        vs = get_vectorstore()
        vs.reset()

        # Load documents from corpus/
        documents = load_corpus()

        # Chunk documents
        chunks = chunk_documents(documents)

        # Embed and index
        count = await index_chunks(chunks)

        return {
            "status": "success",
            "documents_loaded": len(documents),
            "chunks_created": len(chunks),
            "chunks_indexed": count,
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Corpus not found.")
    except Exception as e:
        logger.exception("ingest failed: %s", e)
        raise HTTPException(status_code=500, detail="Ingestion failed.")


@router.post("/ingest/fda")
async def ingest_fda(request: FdaIngestRequest | None = None):
    """Fetch openFDA drug labels and ADD them to the index (deduped by label_id).

    Unlike /ingest this does NOT reset the collection -- it accumulates.
    Known label ids come from Postgres (item 2) when available; otherwise the
    deterministic chunk ids + Chroma upsert still guarantee no duplication.
    """
    req = request or FdaIngestRequest()
    try:
        known = _known_label_ids()
        stats = await run_fda_ingestion(
            drugs=req.drugs, limit=req.limit, known_label_ids=known
        )
        return {"status": "success", **stats}
    except Exception as e:
        logger.exception("openFDA ingestion failed: %s", e)
        raise HTTPException(status_code=502, detail="openFDA ingestion failed.")


class GrowRequest(BaseModel):
    """Optional override for one growth batch."""
    batch_size: int | None = None


@router.post("/ingest/fda/grow")
async def ingest_fda_grow(request: GrowRequest | None = None):
    """Run one daily growth batch (course parity: continuous corpus growth).

    Fetches the next page of newest openFDA labels beyond the stored watermark,
    dedupes by label_id, and indexes the fresh ones. Idempotent + additive.
    """
    req = request or GrowRequest()
    try:
        stats = await run_fda_growth(batch_size=req.batch_size)
        return {"status": "success", **stats}
    except Exception as e:
        logger.exception("openFDA growth failed: %s", e)
        raise HTTPException(status_code=502, detail="openFDA growth failed.")


def _known_label_ids() -> set[str]:
    """Label ids already recorded in Postgres, if persistence is configured.

    Degrades to an empty set when Postgres is unavailable (item 2 wires this up).
    """
    try:
        from app.db import get_known_label_ids
        return get_known_label_ids()
    except Exception:
        return set()
