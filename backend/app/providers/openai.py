"""
OpenAI provider implementation.  [M1]
Uses httpx to call the OpenAI-compatible REST API.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

import httpx

from app.config import get_settings
from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

OPENAI_BASE = "https://api.openai.com/v1"

_RETRY_STATUSES = {429, 500, 502, 503}
_MAX_ATTEMPTS = 5

# text-embedding-3-* cap inputs at 8191 tokens; a few FDA label sections (large
# adverse-reactions / interactions tables) exceed that once the corpus grows,
# which returned a hard 400. Truncate each embedding input to a safe char budget
# (~6k tokens) and never send an empty string. This affects only the embedding
# vector — the full chunk text is still stored and shown in citations.
_MAX_EMBED_CHARS = 24_000


def _prepare_embed_input(text: str) -> str:
    """Clamp an embedding input to a safe, non-empty length."""
    t = (text or "").strip() or " "
    return t[:_MAX_EMBED_CHARS]


async def _post_with_retry(client: httpx.AsyncClient, url: str, payload: dict) -> httpx.Response:
    """POST with exponential backoff on transient errors (429/5xx)."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                delay = 2 ** attempt
                logger.warning(f"OpenAI {e.response.status_code}; retry in {delay}s "
                               f"({attempt + 1}/{_MAX_ATTEMPTS})")
                await asyncio.sleep(delay)
                continue
            raise
        except (httpx.TransportError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < _MAX_ATTEMPTS - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    assert last_exc is not None
    raise last_exc


class OpenAIProvider(LLMProvider):
    """OpenAI provider via REST API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.gen_model = settings.gen_model or "gpt-4.1-mini"
        self.embed_model = settings.embed_model or "text-embedding-3-large"
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        self._client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        url = f"{OPENAI_BASE}/embeddings"
        payload = {"model": self.embed_model, "input": _prepare_embed_input(text)}
        resp = await _post_with_retry(self._client, url, payload)
        return resp.json()["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts."""
        url = f"{OPENAI_BASE}/embeddings"
        payload = {"model": self.embed_model,
                   "input": [_prepare_embed_input(t) for t in texts]}
        resp = await _post_with_retry(self._client, url, payload)
        data = resp.json()["data"]
        # Sort by index to maintain order
        data.sort(key=lambda x: x["index"])
        return [d["embedding"] for d in data]

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens from OpenAI chat completions."""
        url = f"{OPENAI_BASE}/chat/completions"
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
        url = f"{OPENAI_BASE}/chat/completions"
        payload = {
            "model": self.gen_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 2048,
        }
        resp = await _post_with_retry(self._client, url, payload)
        data = resp.json()
        return data["choices"][0]["message"]["content"]
