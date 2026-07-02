"""
Groq provider implementation.  [M1]
Uses httpx to call the Groq API (OpenAI-compatible endpoint).
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from app.config import get_settings
from app.providers.base import LLMProvider

GROQ_BASE = "https://api.groq.com/openai/v1"


class GroqProvider(LLMProvider):
    """Groq provider via OpenAI-compatible REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.groq_api_key
        self.gen_model = settings.gen_model or "llama-3.1-8b-instant"
        self.embed_model = settings.embed_model or "nomic-embed-text"
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def embed(self, text: str) -> list[float]:
        """Embed a single text. Groq does not natively support embeddings,
        so we fall back to a local sentence-transformers model."""
        return await self._local_embed([text])[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch using local sentence-transformers (Groq lacks embed API)."""
        return self._local_embed(texts)

    def _local_embed(self, texts: list[str]) -> list[list[float]]:
        """Use sentence-transformers for embeddings since Groq doesn't offer them."""
        try:
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(texts, show_progress_bar=False)
            return [e.tolist() for e in embeddings]
        except ImportError:
            raise RuntimeError(
                "sentence-transformers required for Groq embeddings. "
                "Install with: pip install sentence-transformers"
            )

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens from Groq (OpenAI-compatible SSE)."""
        url = f"{GROQ_BASE}/chat/completions"
        payload = {
            "model": self.gen_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        async with self._client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        yield delta["content"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue

    async def complete(self, prompt: str) -> str:
        """Non-streaming completion."""
        url = f"{GROQ_BASE}/chat/completions"
        payload = {
            "model": self.gen_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
