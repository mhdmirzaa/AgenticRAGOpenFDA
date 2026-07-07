"""
Security controls: API-key auth, rate limiting, caller identity.  [security-hardening]

A single FastAPI dependency `security_gate` fronts the cost/mutating endpoints:
  1. Authenticate the caller by `X-API-Key` (when AUTH_ENABLED) — 401 on missing/bad.
  2. Rate-limit per-caller AND per-IP with a fixed-window counter (Redis when
     REDIS_URL is set, else in-process) — 429 with Retry-After.
  3. Record a stable, non-reversible caller id in a contextvar so downstream code
     (session/trace ownership) can bind resources to the caller without threading
     it through the whole agent.

Everything is toggle-gated so local dev and the offline test suite run unchanged
(AUTH_ENABLED=0, and the limiter is generous). No new dependency: the limiter
talks to the existing Redis client, or falls back to a small in-memory window.
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import time

from fastapi import HTTPException, Request

from app.config import get_settings

logger = logging.getLogger(__name__)

# The authenticated caller for the current request ("anon" when auth is off).
# ContextVars propagate into the request's async tasks, so the agent's trace
# persistence can read it without an explicit parameter.
current_caller: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_caller", default="anon"
)

ANON = "anon"


# --------------------------------------------------------------------- identity
def caller_id_from_key(key: str) -> str:
    """A stable, non-reversible short id for an API key.

    Used for ownership binding + logs so the raw secret is never stored or logged.
    """
    return "k_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _valid_keys() -> set[str]:
    raw = get_settings().api_keys or ""
    return {k.strip() for k in raw.split(",") if k.strip()}


def client_ip(request: Request) -> str:
    """Best-effort client IP (first hop of X-Forwarded-For behind a proxy)."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- rate limiter
class _MemoryLimiter:
    name = "memory"

    def __init__(self) -> None:
        self._hits: dict[str, int] = {}
        self._last_gc = 0.0

    def incr(self, key: str, window: int) -> int:
        now = time.time()
        slot = int(now // window)
        k = f"{key}:{slot}"
        self._hits[k] = self._hits.get(k, 0) + 1
        # Opportunistic GC of stale windows so memory can't grow unbounded.
        if now - self._last_gc > window:
            self._last_gc = now
            cutoff = slot - 1
            for existing in [x for x in self._hits if int(x.rsplit(":", 1)[1]) < cutoff]:
                self._hits.pop(existing, None)
        return self._hits[k]


class _RedisLimiter:
    name = "redis"

    def __init__(self, client) -> None:
        self._r = client

    def incr(self, key: str, window: int) -> int:
        slot = int(time.time() // window)
        k = f"rl:{key}:{slot}"
        try:
            count = int(self._r.incr(k))
            if count == 1:
                self._r.expire(k, window * 2)
            return count
        except Exception:  # noqa: BLE001 - a limiter outage must not 500 the app
            return 1  # fail-open on a transient Redis error (availability > strictness)


_limiter = None


def get_limiter():
    """The active rate-limit store (Redis when reachable, else memory)."""
    global _limiter
    if _limiter is not None:
        return _limiter
    url = get_settings().redis_url
    if url:
        try:
            import redis  # lazy: already a dependency (cache backend)

            client = redis.Redis.from_url(url, decode_responses=True)
            client.ping()
            _limiter = _RedisLimiter(client)
            return _limiter
        except Exception as e:  # noqa: BLE001
            logger.warning("rate-limiter Redis unavailable (%s); using memory", e)
    _limiter = _MemoryLimiter()
    return _limiter


def reset_limiter() -> None:
    """Drop the limiter singleton (tests / config changes)."""
    global _limiter
    _limiter = None


_WINDOW = 60  # seconds — a per-minute fixed window


def _limit_for(path: str) -> int:
    """Requests/minute allowed for a path class (0 = unlimited)."""
    s = get_settings()
    if path.startswith("/chat") or path.startswith("/ask-agentic"):
        return s.rate_limit_llm_per_min
    if path.startswith("/ingest"):
        return s.rate_limit_ingest_per_min
    return s.rate_limit_default_per_min


def _enforce_rate_limit(request: Request, caller: str) -> None:
    s = get_settings()
    if not s.rate_limit_enabled:
        return
    limit = _limit_for(request.url.path)
    if limit <= 0:
        return
    limiter = get_limiter()
    ip = client_ip(request)
    # A path-class prefix keeps LLM/ingest/default buckets independent.
    cls = request.url.path.split("/", 2)[1] if "/" in request.url.path else "root"
    # Enforce per-IP always; per-key too when authenticated.
    identities = [f"ip:{ip}"]
    if caller != ANON:
        identities.append(f"key:{caller}")
    for ident in identities:
        count = limiter.incr(f"{cls}:{ident}", _WINDOW)
        if count > limit:
            logger.warning("rate limit exceeded: %s on %s (%d/%d)",
                           ident, request.url.path, count, limit)
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please slow down and try again shortly.",
                headers={"Retry-After": str(_WINDOW)},
            )


# ------------------------------------------------------------------ the gate
async def security_gate(request: Request) -> str:
    """Authenticate + rate-limit a request; returns the caller id.

    Wire as a router/endpoint dependency. Raises 401 (bad/missing key) or 429
    (over limit). /health is intentionally NOT gated.
    """
    settings = get_settings()

    caller = ANON
    if settings.auth_enabled:
        key = request.headers.get("x-api-key", "")
        if not key or key not in _valid_keys():
            raise HTTPException(status_code=401, detail="Missing or invalid API key.")
        caller = caller_id_from_key(key)

    current_caller.set(caller)
    _enforce_rate_limit(request, caller)
    return caller
