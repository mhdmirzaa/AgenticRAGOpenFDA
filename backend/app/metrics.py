"""
Lightweight in-process metrics (production-hardening item 3).

Collects request counts, error rate, latency (p50/p95), and agent outcomes
(answers / refusals / blocked), and renders them in Prometheus text format at
`/metrics`. Cache-hit ratio is pulled from the existing cache stats. No new
dependency and no external time source at import — a single-process counter that
a Prometheus scraper (or a human) can read.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start = time.time()
        # (path_class, status) -> count
        self._requests: dict[tuple[str, int], int] = defaultdict(int)
        # path_class -> recent latency samples (ms)
        self._latency: dict[str, deque] = defaultdict(lambda: deque(maxlen=1024))
        self._answers = 0
        self._refusals = 0
        self._blocked = 0

    def record_request(self, path_class: str, status: int, latency_ms: float) -> None:
        with self._lock:
            self._requests[(path_class, status)] += 1
            self._latency[path_class].append(latency_ms)

    def record_outcome(self, *, refused: bool, blocked: bool) -> None:
        with self._lock:
            if blocked:
                self._blocked += 1
            elif refused:
                self._refusals += 1
            else:
                self._answers += 1

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
            self._latency.clear()
            self._answers = self._refusals = self._blocked = 0
            self._start = time.time()

    @staticmethod
    def _pct(samples: list[float], p: float) -> float:
        if not samples:
            return 0.0
        s = sorted(samples)
        k = (len(s) - 1) * p
        f = int(k)
        c = min(f + 1, len(s) - 1)
        return round(s[f] + (s[c] - s[f]) * (k - f), 2)

    def snapshot(self) -> dict:
        """A JSON-friendly view (also used by tests)."""
        with self._lock:
            total = sum(self._requests.values())
            errors = sum(c for (_, st), c in self._requests.items() if st >= 500)
            answered = self._answers + self._refusals + self._blocked
            lat = {p: {"p50": self._pct(list(s), 0.5), "p95": self._pct(list(s), 0.95)}
                   for p, s in self._latency.items()}
            return {
                "requests_total": total,
                "errors_total": errors,
                "error_rate": round(errors / total, 4) if total else 0.0,
                "answers_total": self._answers,
                "refusals_total": self._refusals,
                "blocked_total": self._blocked,
                "refusal_rate": round(self._refusals / answered, 4) if answered else 0.0,
                "latency_ms": lat,
                "uptime_seconds": round(time.time() - self._start, 1),
            }

    def render_prometheus(self) -> str:
        """Prometheus text exposition format."""
        from app.retrieval.cache import cache_stats, answer_cache_stats

        with self._lock:
            lines: list[str] = []
            lines.append("# HELP maistorage_requests_total Total HTTP requests by path class + status.")
            lines.append("# TYPE maistorage_requests_total counter")
            for (path, status), count in sorted(self._requests.items()):
                lines.append(f'maistorage_requests_total{{path="{path}",status="{status}"}} {count}')

            lines.append("# HELP maistorage_request_latency_ms Request latency quantiles (ms) by path class.")
            lines.append("# TYPE maistorage_request_latency_ms gauge")
            for path, samples in sorted(self._latency.items()):
                data = list(samples)
                for q in (0.5, 0.95):
                    lines.append(
                        f'maistorage_request_latency_ms{{path="{path}",quantile="{q}"}} '
                        f'{self._pct(data, q)}')

            for name, val, help_ in (
                ("maistorage_answers_total", self._answers, "Agent answers produced."),
                ("maistorage_refusals_total", self._refusals, "Agent refusals (incl. unanswerable)."),
                ("maistorage_blocked_total", self._blocked, "Guardrail-blocked requests."),
            ):
                lines.append(f"# HELP {name} {help_}")
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {val}")

        # Cache hit ratios (from the existing cache stats; degrade-safe).
        try:
            lines.append("# HELP maistorage_cache_hit_ratio Cache hit ratio (0-1).")
            lines.append("# TYPE maistorage_cache_hit_ratio gauge")
            lines.append(f'maistorage_cache_hit_ratio{{cache="retrieval"}} {cache_stats().get("hit_ratio", 0.0)}')
            lines.append(f'maistorage_cache_hit_ratio{{cache="answer"}} {answer_cache_stats().get("hit_ratio", 0.0)}')
        except Exception:
            pass
        return "\n".join(lines) + "\n"


_metrics = Metrics()


def get_metrics() -> Metrics:
    return _metrics
