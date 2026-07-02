"""
Provider-agnostic LLM layer.  [M1]

Protocol LLMProvider: embed(text)->vec, generate_stream(prompt)->async gen,
complete(prompt)->str.
get_provider() reads LLM_PROVIDER and returns the right impl.
RULE: all agent/retrieval/api code calls get_provider() -- never a vendor SDK directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator

from app.config import get_settings


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return embedding vector for the given text."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for a batch of texts."""
        ...

    @abstractmethod
    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Yield tokens one at a time as they are generated."""
        ...

    @abstractmethod
    async def complete(self, prompt: str) -> str:
        """Return a complete response string (non-streaming)."""
        ...


_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Singleton: return the configured LLM provider instance."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    settings = get_settings()
    provider_name = settings.llm_provider.lower()

    if provider_name == "gemini":
        from app.providers.gemini import GeminiProvider
        _provider_instance = GeminiProvider()
    elif provider_name == "ollama":
        from app.providers.ollama import OllamaProvider
        _provider_instance = OllamaProvider()
    elif provider_name == "openai":
        from app.providers.openai import OpenAIProvider
        _provider_instance = OpenAIProvider()
    elif provider_name == "groq":
        from app.providers.groq import GroqProvider
        _provider_instance = GroqProvider()
    elif provider_name == "local":
        from app.providers.local import LocalProvider
        _provider_instance = LocalProvider()
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider_name}")

    return _provider_instance


def reset_provider() -> None:
    """Reset provider singleton (for testing)."""
    global _provider_instance
    _provider_instance = None
