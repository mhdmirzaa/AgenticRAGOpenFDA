"""
Tests for the Telegram bot service (PRD v3.0 §9.2, M7).

The message-processing logic is decoupled from python-telegram-bot so it is
unit-testable with a mocked backend: async call to /ask-agentic, graceful
failure on backend error, answer + sources formatting, and safe-disable when the
token is absent.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.telegram.handlers import answer_question, _format_answer, DISCLAIMER
from app.services.telegram import bot as bot_mod


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    """Stand-in httpx.AsyncClient that returns a canned /ask-agentic payload."""
    def __init__(self, payload=None, boom=False):
        self.payload = payload
        self.boom = boom
        self.posted = None

    async def post(self, url, json=None):
        self.posted = (url, json)
        if self.boom:
            raise RuntimeError("backend down")
        return _FakeResp(self.payload)


def test_answer_question_forwards_and_formats():
    payload = {
        "answer": "Ibuprofen may cause stomach bleeding [1].",
        "citations": [{"marker": "[1]", "source": "IBUPROFEN",
                       "section": "warnings", "section_title": "Warnings"}],
        "trace_id": "t1", "refused": False, "blocked": False,
    }
    client = _FakeClient(payload)
    reply = asyncio.run(answer_question("warnings for ibuprofen?", session_id="tg-1",
                                        client=client))
    assert "stomach bleeding" in reply
    assert "IBUPROFEN" in reply and "Warnings" in reply
    # It hit the agentic endpoint with the question + session.
    url, body = client.posted
    assert url.endswith("/ask-agentic")
    assert body["question"] == "warnings for ibuprofen?"
    assert body["session_id"] == "tg-1"


def test_answer_question_degrades_on_backend_error():
    client = _FakeClient(boom=True)
    reply = asyncio.run(answer_question("anything", client=client))
    # Graceful failure message, never raises.
    assert "couldn't reach" in reply.lower()
    assert DISCLAIMER.strip() in reply


def test_format_answer_dedupes_sources():
    payload = {
        "answer": "A [1][2].",
        "citations": [
            {"marker": "[1]", "source": "X", "section": "warnings", "section_title": "Warnings"},
            {"marker": "[2]", "source": "X", "section": "warnings", "section_title": "Warnings"},
        ],
    }
    out = _format_answer(payload)
    # The duplicate (X#warnings) source line appears once.
    assert out.count("X — Warnings") == 1


def test_bot_disabled_without_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM__BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    # No token -> main() returns 0 cleanly (no crash, bot simply doesn't start).
    assert bot_mod.get_token() == ""
    assert bot_mod.main() == 0
