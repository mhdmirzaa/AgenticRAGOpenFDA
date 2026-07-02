"""POST /ingest -- [M2]. (Re)build the Chroma index from corpus/."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.ingestion.loader import load_corpus
from app.ingestion.chunker import chunk_documents
from app.ingestion.indexer import index_chunks
from app.retrieval.vectorstore import get_vectorstore

router = APIRouter()


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
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")
