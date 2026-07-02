"""
Langfuse observability.  [production item 8]

Traces every agent request (each node, retrieved chunk ids, the LLM prompt +
response, estimated token counts, latency, and cost) to a self-hosted Langfuse.

Guardrail: instrumentation must NEVER break a user request. If Langfuse is not
configured (no keys), unreachable, or the SDK is missing, everything degrades to
a no-op transparently.
"""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)


# Rough public per-1K-token USD rates (gpt-4.1-mini) for a demo cost estimate.
_COST_PER_1K = {
    "gpt-4.1-mini": {"in": 0.0004, "out": 0.0016},
}


def estimate_tokens(text: str) -> int:
    """Cheap token estimate (~4 chars/token) when the provider gives no usage."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_cost(model: str, in_tokens: int, out_tokens: int) -> float:
    """Rough USD cost estimate for a generation (0.0 for unknown models)."""
    rate = _COST_PER_1K.get(model)
    if not rate:
        return 0.0
    return round((in_tokens / 1000) * rate["in"] + (out_tokens / 1000) * rate["out"], 6)


class _NoOpTrace:
    """Silent stand-in used whenever Langfuse is off/unreachable."""

    def span(self, *args, **kwargs) -> None:
        pass

    def update(self, *args, **kwargs) -> None:
        pass

    def end(self) -> None:
        pass


class _LangfuseTrace:
    """Thin wrapper; every call is defensive so tracing can't break a request."""

    def __init__(self, client, trace) -> None:
        self._client = client
        self._trace = trace

    def span(self, name, input=None, output=None, metadata=None) -> None:
        try:
            self._trace.span(name=name, input=input, output=output, metadata=metadata)
        except Exception as e:  # pragma: no cover - defensive
            logger.debug("langfuse span failed: %s", e)

    def update(self, output=None, metadata=None) -> None:
        try:
            self._trace.update(output=output, metadata=metadata)
        except Exception as e:  # pragma: no cover
            logger.debug("langfuse update failed: %s", e)

    def end(self) -> None:
        try:
            self._client.flush()
        except Exception as e:  # pragma: no cover
            logger.debug("langfuse flush failed: %s", e)


class Observer:
    """Lazily-initialized Langfuse client; disabled = no-op."""

    def __init__(self) -> None:
        self._client = None
        s = get_settings()
        if s.langfuse_public_key and s.langfuse_secret_key:
            try:
                from langfuse import Langfuse  # optional dependency
                kwargs = {
                    "public_key": s.langfuse_public_key,
                    "secret_key": s.langfuse_secret_key,
                }
                if s.langfuse_host:
                    kwargs["host"] = s.langfuse_host
                self._client = Langfuse(**kwargs)
                logger.info("Langfuse observability enabled (host=%s)", s.langfuse_host or "cloud")
            except Exception as e:
                logger.warning("Langfuse init failed (tracing disabled): %s", e)
                self._client = None

    def enabled(self) -> bool:
        return self._client is not None

    def start_trace(self, name: str, input=None, metadata=None):
        """Begin a trace; returns a handle (no-op when disabled)."""
        if self._client is None:
            return _NoOpTrace()
        try:
            trace = self._client.trace(name=name, input=input, metadata=metadata)
            return _LangfuseTrace(self._client, trace)
        except Exception as e:  # pragma: no cover
            logger.debug("langfuse trace start failed: %s", e)
            return _NoOpTrace()


_observer: Observer | None = None


def get_observer() -> Observer:
    """Singleton observer. Never raises."""
    global _observer
    if _observer is None:
        try:
            _observer = Observer()
        except Exception as e:  # pragma: no cover
            logger.warning("observer init failed: %s", e)
            _observer = Observer.__new__(Observer)
            _observer._client = None  # type: ignore[attr-defined]
    return _observer


def reset_observer() -> None:
    """Drop the observer singleton (tests / config changes)."""
    global _observer
    _observer = None
