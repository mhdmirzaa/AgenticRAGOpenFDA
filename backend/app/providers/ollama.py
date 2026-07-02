"""
Ollama provider implementation.  [M1]
Local/offline fallback using Ollama HTTP API.
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

import httpx

from app.config import get_settings
from app.providers.base import LLMProvider

OLLAMA_BASE = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    """Ollama local provider (no API key needed)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.gen_model = settings.gen_model or "llama3.1:8b"
        self.embed_model = settings.embed_model or "nomic-embed-text"
        self._client = httpx.AsyncClient(timeout=120.0)

    async def embed(self, text: str) -> list[float]:
        """Embed a single text."""
        url = f"{OLLAMA_BASE}/api/embed"
        payload = {"model": self.embed_model, "input": text}
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"][0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed batch of texts (Ollama supports batch in /api/embed)."""
        url = f"{OLLAMA_BASE}/api/embed"
        payload = {"model": self.embed_model, "input": texts}
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["embeddings"]

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens from Ollama."""
        url = f"{OLLAMA_BASE}/api/generate"
        payload = {
            "model": self.gen_model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": 0.2},
        }
        async with self._client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    if data.get("done"):
                        break
                    if "response" in data:
                        yield data["response"]
                except json.JSONDecodeError:
                    continue

    async def complete(self, prompt: str) -> str:
        """Non-streaming completion."""
        url = f"{OLLAMA_BASE}/api/generate"
        payload = {
            "model": self.gen_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.1},
        }
        resp = await self._client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json().get("response", "")
