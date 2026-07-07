"""
FastAPI app entrypoint.  [M1; warm-up wired in M3]

- create app, add CORS for http://localhost:3000
- include routers: health, ingest, chat, trace
- startup: warm up the configured provider and check Chroma.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.metrics import router as metrics_router
from app.api.ingest import router as ingest_router
from app.api.chat import router as chat_router
from app.api.ask import router as ask_router
from app.api.trace import router as trace_router
from app.api.sessions import router as sessions_router
from app.config import get_settings
from app.security import security_gate

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    # Structured logging (JSON in prod) before anything else logs (item 3).
    try:
        from app.logging_config import configure_logging
        configure_logging(settings.json_logs)
    except Exception:  # noqa: BLE001 - logging setup must never block startup
        pass
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

    # Primary store: OpenSearch when configured (course parity); otherwise the
    # embedded Chroma fallback (with a pre-built BM25 keyword index).
    try:
        from app.retrieval.opensearch_store import get_opensearch_store
        os_store = get_opensearch_store()
        if os_store is not None:
            logger.info(f"OpenSearch ready with {os_store.count()} documents")
        else:
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
        logger.warning(f"Store check failed: {e}")
    
    # Optional in-process ingestion scheduler (APScheduler fallback for Airflow).
    try:
        from app.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start skipped: {e}")

    yield

    try:
        from app.scheduler import shutdown_scheduler
        shutdown_scheduler()
    except Exception:
        pass
    logger.info("Shutting down MaiStorage")


app = FastAPI(
    title="MaiStorage Agentic RAG",
    description="An agentic RAG system with self-grading retrieval, citations, and graceful refusal",
    version="0.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_id_and_errors(request, call_next):
    """Tag every request with an id, record metrics + a structured access log,
    and convert unhandled errors to a generic 500 (security item 8 + observability
    item 3). No stack trace / internal detail ever reaches the client — the real
    error is logged server-side against the request id.
    """
    import time as _time
    import uuid as _uuid
    from fastapi.responses import JSONResponse
    from app.metrics import get_metrics

    rid = _uuid.uuid4().hex[:16]
    request.state.request_id = rid
    path = request.url.path
    path_class = path.split("/", 2)[1] if "/" in path[1:] else (path.strip("/") or "root")
    started = _time.perf_counter()
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception:  # noqa: BLE001 - never leak internals to the client
        logger.exception("unhandled error [rid=%s] %s %s", rid, request.method, path)
        response = JSONResponse(
            {"detail": "Internal server error.", "request_id": rid},
            status_code=500,
        )
        status = 500

    latency_ms = round((_time.perf_counter() - started) * 1000, 2)
    get_metrics().record_request(path_class, status, latency_ms)
    # Structured access log (JSON when JSON_LOGS=1). Never logs the request body.
    logger.info(
        "request",
        extra={"request_id": rid, "method": request.method, "path": path,
               "status": status, "latency_ms": latency_ms},
    )
    response.headers["X-Request-ID"] = rid
    return response


@app.middleware("http")
async def security_headers(request, call_next):
    """Attach hardening headers to every API response (security item 4).

    The API returns JSON/SSE only, so a locked-down CSP (`default-src 'none'`) is
    safe here and blunts any content-sniffing / clickjacking / referrer leakage.
    HSTS is added only in the prod (TLS) profile via HSTS_ENABLED.
    """
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
    )
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if get_settings().hsts_enabled:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
    return response


@app.middleware("http")
async def limit_request_body(request, call_next):
    """Reject oversized request bodies early (security item 3 — DoS/abuse).

    A declared Content-Length over the cap is refused with 413 before the body is
    read into memory.
    """
    from fastapi.responses import JSONResponse
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > get_settings().max_body_bytes:
        return JSONResponse({"detail": "Request body too large."}, status_code=413)
    return await call_next(request)

# CORS — explicit frontend-origin allowlist (never "*" with credentials). The
# origins come from config (CORS_ORIGINS); add the prod origin there for deploy.
_cors_origins = [o.strip() for o in get_settings().cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# /health is PUBLIC (no auth/rate-limit). Every cost/mutating router is gated by
# `security_gate` (API-key auth when AUTH_ENABLED + per-caller/per-IP rate limit).
_gate = [Depends(security_gate)]
app.include_router(health_router, tags=["health"])
app.include_router(metrics_router, tags=["metrics"])  # public (like /health)
app.include_router(ingest_router, tags=["ingestion"], dependencies=_gate)
app.include_router(chat_router, tags=["chat"], dependencies=_gate)
app.include_router(ask_router, tags=["chat"], dependencies=_gate)
app.include_router(trace_router, tags=["trace"], dependencies=_gate)
app.include_router(sessions_router, tags=["sessions"], dependencies=_gate)
