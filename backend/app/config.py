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

    # API keys (optional depending on provider)
    gemini_api_key: str = ""
    openai_api_key: str = ""
    groq_api_key: str = ""

    # openFDA is keyless by default; a key only raises rate limits.
    openfda_api_key: str = ""

    # Chroma vector DB
    chroma_path: str = "./chroma_db"

    # PostgreSQL persistence (item 2). Defaults to a local sqlite file so the
    # app + tests run with zero external services; docker-compose sets a
    # postgresql+psycopg:// URL.
    database_url: str = "sqlite:///./maistorage.db"

    # last-N prior messages loaded as conversation memory
    memory_window: int = 6

    # Orchestration (item 3). Airflow is the production orchestrator; the
    # in-process APScheduler is the runnable fallback. Off by default.
    enable_scheduler: bool = False
    schedule_minutes: int = 15

    # Caching (item 7). Empty REDIS_URL => in-memory LRU (degrades gracefully).
    redis_url: str = ""
    cache_ttl_seconds: int = 3600

    # Retrieval params
    top_k: int = 8
    rerank_top_n: int = 4
    max_iters: int = 3  # agent loop hard cap

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
