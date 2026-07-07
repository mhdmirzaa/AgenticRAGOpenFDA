"""
Settings & environment config.  [Milestone M1]
Loads LLM_PROVIDER, API keys, model names, Chroma path, and retrieval params.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # LLM provider
    llm_provider: str = "gemini"  # gemini | openai | groq | ollama
    gen_model: str = "gemini-2.5-flash-lite"
    # NOTE: the Gemini *AI Studio* (generativelanguage) API exposes
    # gemini-embedding-001, NOT the Vertex-only text-embedding-00x names.
    embed_model: str = "gemini-embedding-001"

    # Embedding dimension. text-embedding-3-large = 3072; -3-small = 1536;
    # gemini-embedding-001 = 3072. Only used to size the OpenSearch knn_vector
    # field (Chroma infers dimension from the first vector). [PRD v3.0 M1]
    embed_dim: int = 3072

    # API keys (optional depending on provider)
    gemini_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""

    # openFDA is keyless by default; a key only raises rate limits.
    openfda_api_key: str = ""

    # Chroma vector DB (fallback store when OpenSearch is not configured)
    chroma_path: str = "./chroma_db"

    # OpenSearch (course-parity primary store: BM25 + kNN, native hybrid RRF).
    # Empty => fall back to Chroma + rank-bm25 (keeps offline tests green and
    # preserves a revert path). [PRD v3.0 M2]
    opensearch_url: str = ""              # e.g. http://opensearch:9200
    opensearch_index: str = "fda_labels"
    opensearch_user: str = ""
    opensearch_password: str = ""

    # PostgreSQL persistence (item 2). Defaults to a local sqlite file so the
    # app + tests run with zero external services; docker-compose sets a
    # postgresql+psycopg:// URL.
    database_url: str = "sqlite:///./maistorage.db"

    # last-N prior messages loaded as conversation memory
    memory_window: int = 6

    # Orchestration (item 3). Airflow is the production orchestrator; the
    # in-process APScheduler is the runnable fallback. Off by default.
    enable_scheduler: bool = False
    schedule_minutes: int = 1440  # daily fallback (course parity: daily sync)

    # Continuous corpus growth (course parity: daily openFDA sync). One growth
    # batch fetches the newest labels beyond a stored watermark. [PRD v3.0 M3]
    growth_batch_size: int = 25   # labels fetched per growth run

    # Telegram bot (secondary client). Empty token => bot does not start. The
    # course names this TELEGRAM__BOT_TOKEN; both spellings are accepted. [M7]
    telegram_bot_token: str = ""

    # Safety guardrail (medical domain). First node in the graph. [PRD v3.0 M4a]
    enable_guardrail: bool = True

    # ---- Security (security-hardening pass) ----------------------------------
    # API-key auth on cost/mutating endpoints. OFF by default so local dev + the
    # offline test suite work unchanged; the prod compose profile sets it ON.
    auth_enabled: bool = False
    # Comma-separated accepted keys (X-API-Key). Env only, never hardcode.
    api_keys: str = ""
    # Rate limiting (fixed-window; Redis-backed when REDIS_URL set, else memory).
    # OFF by default (like auth) so the offline suite + local dev aren't throttled;
    # the prod compose profile sets it ON alongside AUTH_ENABLED.
    rate_limit_enabled: bool = False
    rate_limit_llm_per_min: int = 20      # /chat, /ask-agentic (LLM cost)
    rate_limit_ingest_per_min: int = 5    # /ingest* (expensive)
    rate_limit_default_per_min: int = 120  # /sessions, /trace, other authed
    # Input caps (DoS + prompt-bloat defense). Enforced by Pydantic + middleware.
    max_question_chars: int = 4000
    max_body_bytes: int = 65_536          # 64 KB request-body ceiling
    # CORS allowlist — explicit origins only (never "*" with credentials).
    cors_origins: str = "http://localhost:3000,http://localhost:8501"
    # HSTS (prod only; behind TLS termination). Off by default for plain-HTTP dev.
    hsts_enabled: bool = False
    # Telegram webhook shared secret (when running in webhook mode, not polling).
    telegram_webhook_secret: str = ""
    # API key the Telegram bot presents to the backend when AUTH_ENABLED.
    backend_api_key: str = ""

    # Caching (item 7). Empty REDIS_URL => in-memory LRU (degrades gracefully).
    redis_url: str = ""
    cache_ttl_seconds: int = 3600

    # Final-answer cache (v3.2 performance). An exact-repeat question (same mode,
    # no conversation history) returns the whole answer instantly, skipping the
    # ~10 s generation. Short TTL keeps answers fresh; degrade-safe (any cache
    # error just recomputes). Disable with ENABLE_ANSWER_CACHE=0.
    enable_answer_cache: bool = True
    answer_cache_ttl_seconds: int = 300

    # Observability (item 8). Empty keys => tracing no-ops (degrades gracefully).
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = ""

    # Metadata-scoped retrieval (scoped-retrieval branch). Restrict the candidate
    # set to the drug(s) a question is about BEFORE similarity search, removing
    # cross-drug hard negatives on the homogeneous FDA-label corpus (§14). Fully
    # degrade-safe: unresolved -> unfiltered; scoped-too-few -> auto-retry
    # unfiltered (never below today's recall). Disable with ENABLE_SCOPING=0.
    enable_scoping: bool = True
    # If a scoped search returns fewer than this many candidates, retry UNFILTERED
    # (a drug barely represented in the index must never starve retrieval).
    scope_min_results: int = 3

    # Retrieval params
    top_k: int = 8
    rerank_top_n: int = 4
    # Grade at most this many reranked candidates (0 = grade all of them). A
    # latency/token lever (v3.2): with batched grading it shrinks the single
    # grader prompt; the default 0 preserves the "grade every reranked chunk"
    # behavior so evidence/citations are unchanged.
    grade_top_n: int = 0
    max_iters: int = 3  # agent loop hard cap

    # Hybrid RRF fusion weights (ENHANCE item 2: retrieval robustness).
    # With the strong text-embedding-3-large model, dense is the more reliable
    # signal on this clean, curated corpus, so fusion favors it and BM25 only
    # adds lexical recall — a doc that is dense-unique at a rank outranks a
    # BM25-unique doc at the same rank. Combined with the dense-anchor guard
    # (the single strongest dense hit is never dropped by fusion), this keeps
    # the optimized path from scoring below the dense-only baseline.
    rrf_dense_weight: float = 1.0
    rrf_bm25_weight: float = 0.5

    # Corpus path
    corpus_path: str = str(Path(__file__).resolve().parent.parent.parent / "corpus")

    # Load .env from the project root regardless of the current working
    # directory (the app can be launched from root, backend/, or eval/).
    model_config = {
        "env_file": str(Path(__file__).resolve().parents[2] / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings instance."""
    return Settings()
