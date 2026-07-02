"""
Local embedding provider.  [offline path]

Uses a local sentence-transformers model (all-MiniLM-L6-v2) for embeddings so
retrieval works with ZERO API keys and ZERO network — the true $0/offline story
from the PRD (a stand-in for nomic-embed-text). This provider is EMBEDDING-ONLY:
generation requires a real chat LLM, so complete()/generate_stream() raise a
clear error directing you to set a chat-capable LLM_PROVIDER (gemini/ollama/...).
"""

from __future__ import annotations

from typing import AsyncGenerator

from app.config import get_settings
from app.providers.base import LLMProvider

_DEFAULT_LOCAL_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

_NO_GEN_MSG = (
    "LLM_PROVIDER=local is embedding-only. Set a chat-capable provider "
    "(gemini/ollama/openai/groq) for answer generation."
)


class LocalProvider(LLMProvider):
    """Embedding-only provider backed by a local sentence-transformers model."""

    def __init__(self, model_name: str | None = None) -> None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        name = model_name or settings.embed_model
        # If the configured embed model isn't a local ST model, fall back.
        if "/" not in name and not name.startswith("all-"):
            name = _DEFAULT_LOCAL_MODEL
        self._model = SentenceTransformer(name)

    async def embed(self, text: str) -> list[float]:
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        vecs = self._model.encode(list(texts), normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        raise NotImplementedError(_NO_GEN_MSG)
        yield  # pragma: no cover  (makes this an async generator)

    async def complete(self, prompt: str) -> str:
        raise NotImplementedError(_NO_GEN_MSG)
