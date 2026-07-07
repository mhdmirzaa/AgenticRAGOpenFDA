"""
Observability: /metrics endpoint + structured JSON logging (production item 3).
"""

import json
import logging
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tests.test_e2e import FakeProvider


def _clear():
    from app.config import get_settings
    get_settings.cache_clear()
    from app.security import reset_limiter
    reset_limiter()


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    tmp = tempfile.mkdtemp(prefix="maistorage_metrics_")
    prev = {k: os.environ.get(k) for k in ("CHROMA_PATH", "LLM_PROVIDER", "DATABASE_URL")}
    os.environ.update({"CHROMA_PATH": tmp, "LLM_PROVIDER": "local",
                       "DATABASE_URL": f"sqlite:///{tmp}/m.db"})
    _clear()
    from app.providers import base as provider_base
    from app.db import reset_engine
    from app.metrics import get_metrics
    reset_engine()
    get_metrics().reset()
    provider_base._provider_instance = FakeProvider()
    from app.main import app
    with TestClient(app) as c:
        yield c
    provider_base.reset_provider()
    reset_engine()
    for k, v in prev.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v
    _clear()


def test_metrics_endpoint_is_public_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    assert "maistorage_requests_total" in body
    assert "maistorage_request_latency_ms" in body
    assert "maistorage_refusals_total" in body


def test_metrics_count_increments(client):
    client.get("/health")
    client.get("/health")
    r = client.get("/metrics")
    # health requests are counted under the "health" path class.
    assert 'maistorage_requests_total{path="health",status="200"}' in r.text


def test_metrics_records_refusal(client):
    client.post("/ask-agentic",
                json={"question": "What is the recipe for chocolate lava cake?"})
    snap = None
    from app.metrics import get_metrics
    snap = get_metrics().snapshot()
    # An out-of-domain question refuses -> refusal counter moved.
    assert snap["refusals_total"] >= 1
    assert snap["requests_total"] >= 1


def test_json_formatter_emits_valid_json():
    from app.logging_config import JsonFormatter
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "request", (), None)
    rec.request_id = "abc123"
    rec.path = "/chat"
    rec.status = 200
    line = JsonFormatter().format(rec)
    obj = json.loads(line)
    assert obj["msg"] == "request"
    assert obj["request_id"] == "abc123"
    assert obj["status"] == 200
    assert obj["level"] == "INFO"
