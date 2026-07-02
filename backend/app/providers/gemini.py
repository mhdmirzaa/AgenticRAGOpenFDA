"""
Gemini provider implementation.  [M1]
Uses httpx to call the Gemini REST API for embeddings and generation.
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

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"

# Transient statuses worth retrying on the free tier (overload / rate limit).
_RETRY_STATUSES = {429, 500, 503}
_MAX_ATTEMPTS = 5


async def _post_with_retry(client: httpx.AsyncClient, url: str, payload: dict) -> httpx.Response:
    """POST with exponential backoff on transient Gemini errors (429/500/503)."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                delay = 2 ** attempt  # 1, 2, 4, 8s
                logger.warning(f"Gemini {e.response.status_code}; retry in {delay}s "
                               f"(attempt {attempt + 1}/{_MAX_ATTEMPTS})")
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


def _parse_sse_line(line: str) -> str | None:
    """Extract token text from one Gemini SSE `data:` line, else None."""
    if not line.startswith("data: "):
        return None
    data = line[6:]
    if data.strip() == "[DONE]":
        return None
    try:
        chunk = json.loads(data)
    except json.JSONDecodeError:
        return None
    candidates = chunk.get("candidates", [])
    if not candidates:
        return None
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(p["text"] for p in parts if "text" in p)
    return text or None


class GeminiProvider(LLMProvider):
    """Google Gemini via REST API (free tier compatible)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.gen_model = settings.gen_model
        self.embed_model = settings.embed_model
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
        self._client = httpx.AsyncClient(timeout=60.0)

    async def embed(self, text: str) -> list[float]:
        """Embed a single text string."""
        url = f"{GEMINI_BASE}/models/{self.embed_model}:embedContent?key={self.api_key}"
        payload = {
            "model": f"models/{self.embed_model}",
            "content": {"parts": [{"text": text}]},
        }
        resp = await _post_with_retry(self._client, url, payload)
        return resp.json()["embedding"]["values"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using batchEmbedContents."""
        url = f"{GEMINI_BASE}/models/{self.embed_model}:batchEmbedContents?key={self.api_key}"
        requests = []
        for text in texts:
            requests.append({
                "model": f"models/{self.embed_model}",
                "content": {"parts": [{"text": text}]},
            })
        payload = {"requests": requests}
        resp = await _post_with_retry(self._client, url, payload)
        embeddings = resp.json()["embeddings"]
        return [e["values"] for e in embeddings]

    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream tokens from Gemini generateContent with SSE."""
        url = (
            f"{GEMINI_BASE}/models/{self.gen_model}:streamGenerateContent"
            f"?alt=sse&key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
        }

        # Retry the stream *setup* on transient errors before any token is sent.
        for attempt in range(_MAX_ATTEMPTS):
            try:
                async with self._client.stream("POST", url, json=payload) as resp:
                    if resp.status_code in _RETRY_STATUSES and attempt < _MAX_ATTEMPTS - 1:
                        await resp.aread()
                        await asyncio.sleep(2 ** attempt)
                        continue
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        _emit = _parse_sse_line(line)
                        if _emit is not None:
                            yield _emit
                return
            except (httpx.TransportError, httpx.TimeoutException):
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise

    async def complete(self, prompt: str) -> str:
        """Non-streaming completion."""
        url = (
            f"{GEMINI_BASE}/models/{self.gen_model}:generateContent"
            f"?key={self.api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048},
        }
        resp = await _post_with_retry(self._client, url, payload)
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts)
