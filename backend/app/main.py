"""
FastAPI app entrypoint.  [M1; warm-up wired in M3]

- create app, add CORS for http://localhost:3000
- include routers: health, ingest, chat, trace
- startup: warm up the configured provider and check Chroma.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.chat import router as chat_router
from app.api.trace import router as trace_router
from app.api.sessions import router as sessions_router
from app.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info(f"Starting MaiStorage with provider={settings.llm_provider}")

    # Initialize the persistence layer (Postgres/SQLite). Non-fatal if down.
    try:
        from app.db import init_db
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database init failed (persistence disabled): {e}")

    # Warm up: a throwaway embed + generate so the first real request is fast
    # (loads model weights / opens the HTTP connection / primes any caches).
    try:
        from app.providers.base import get_provider
        provider = get_provider()
        try:
            await provider.embed("warmup")
            _ = await provider.complete("Reply with the single word: ok")
            logger.info(f"Provider {settings.llm_provider} warmed up (embed+generate)")
        except Exception as warm_e:
            logger.warning(f"Provider warm-up call failed (continuing): {warm_e}")
    except Exception as e:
        logger.warning(f"Provider init failed: {e}")

    # Verify Chroma and pre-build the BM25 keyword index for hybrid retrieval.
    try:
        from app.retrieval.vectorstore import get_vectorstore
        vs = get_vectorstore()
        count = vs.count()
        logger.info(f"Chroma ready with {count} documents")
        if count > 0:
            try:
                from app.retrieval.hybrid import get_hybrid_retriever
                get_hybrid_retriever().ensure_index()
                logger.info("BM25 hybrid index pre-built")
            except Exception as bm_e:
                logger.warning(f"BM25 pre-build skipped: {bm_e}")
    except Exception as e:
        logger.warning(f"Chroma check failed: {e}")
    
    yield
    
    logger.info("Shutting down MaiStorage")


app = FastAPI(
    title="MaiStorage Agentic RAG",
    description="An agentic RAG system with self-grading retrieval, citations, and graceful refusal",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS for Next.js / Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, tags=["health"])
app.include_router(ingest_router, tags=["ingestion"])
app.include_router(chat_router, tags=["chat"])
app.include_router(trace_router, tags=["trace"])
app.include_router(sessions_router, tags=["sessions"])
