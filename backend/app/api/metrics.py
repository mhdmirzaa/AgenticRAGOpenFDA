"""GET /metrics — Prometheus-format operational metrics (production item 3).

Public (like /health), non-sensitive aggregates only (counts, latency quantiles,
outcome + cache-hit ratios — no PII, no secrets). Restrict to the internal
network in production (see docs/OPERATIONS.md).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from app.metrics import get_metrics

router = APIRouter()


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return get_metrics().render_prometheus()
