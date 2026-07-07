"""
Structured logging (production-hardening item 3).

`configure_logging(json_logs)` installs a JSON formatter on the root logger when
JSON_LOGS=1 (prod), else a readable plain formatter (dev). Secrets are never
logged by the app (errors log the exception message, not credentials). No new
dependency — a small stdlib `logging.Formatter` subclass.
"""

from __future__ import annotations

import json
import logging


class JsonFormatter(logging.Formatter):
    """One JSON object per log line, with any `extra=` fields merged in."""

    _RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
        "message", "asctime"
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Merge structured extras (e.g. request_id, path, status, latency_ms).
        for k, v in record.__dict__.items():
            if k not in self._RESERVED and not k.startswith("_"):
                payload[k] = v
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(json_logs: bool) -> None:
    """Install the chosen formatter on the root + uvicorn loggers (idempotent)."""
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    fmt: logging.Formatter = (
        JsonFormatter() if json_logs
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    for h in root.handlers:
        h.setFormatter(fmt)
    if root.level == logging.WARNING:  # default -> raise to INFO for access logs
        root.setLevel(logging.INFO)
    # Keep uvicorn's access/error logs consistent with ours.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        lg = logging.getLogger(name)
        for h in lg.handlers:
            h.setFormatter(fmt)
