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

from app.services.telegram.handlers import (
    answer_question, _format_answer, _DISCLAIMER_PLAIN, split_message,
    message_handler, WELCOME, HELP, TELEGRAM_LIMIT,
)
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

    async def post(self, url, json=None, headers=None):
        self.posted = (url, json)
        self.posted_headers = headers
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
    assert _DISCLAIMER_PLAIN.strip() in reply


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


def test_answer_carries_disclaimer_and_sources():
    """A normal answer relays the grounded text + a Sources list; the generated
    answer's medical disclaimer is preserved."""
    payload = {
        "answer": ("Ibuprofen may cause stomach bleeding [1].\n\nInformational only, "
                   "sourced from FDA labels — not medical advice. Consult a healthcare "
                   "professional."),
        "citations": [{"marker": "[1]", "source": "IBUPROFEN",
                       "section": "warnings", "section_title": "Warnings"}],
    }
    reply = asyncio.run(answer_question("q", client=_FakeClient(payload)))
    assert "not medical advice" in reply.lower()
    assert "Sources:" in reply and "IBUPROFEN — Warnings" in reply


def test_guardrail_refusal_is_relayed_not_bypassed():
    """A self-harm question is blocked by the backend guardrail; the bot relays
    the caring refusal verbatim (it must NOT bypass the guardrail)."""
    caring = ("I'm really sorry you're going through this, and I'm not able to help "
              "with anything about overdosing or self-harm. Please reach out … 988 …")
    payload = {"answer": caring, "citations": [], "refused": True, "blocked": True}
    reply = asyncio.run(answer_question("how much would kill me?",
                                        client=_FakeClient(payload)))
    assert "not able to help" in reply
    assert "988" in reply


def test_split_message_short_is_single():
    assert split_message("hello") == ["hello"]


def test_split_message_long_chunks_within_limit():
    # A long multi-line answer splits into <=limit chunks with content preserved.
    body = "\n".join(f"line {i} " + "x" * 100 for i in range(200))  # ~20k chars
    parts = split_message(body, limit=TELEGRAM_LIMIT)
    assert len(parts) > 1
    assert all(len(p) <= TELEGRAM_LIMIT for p in parts)
    # No content lost (line count preserved across the split).
    assert sum(p.count("line ") for p in parts) == 200


def test_split_message_hard_splits_a_giant_line():
    giant = "z" * (TELEGRAM_LIMIT * 2 + 50)
    parts = split_message(giant, limit=TELEGRAM_LIMIT)
    assert all(len(p) <= TELEGRAM_LIMIT for p in parts)
    assert "".join(parts) == giant


# ------------------------------------------------------ message_handler (mocked)
class _Msg:
    def __init__(self, text):
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


class _Bot:
    async def send_chat_action(self, **kwargs):
        return None


class _Update:
    def __init__(self, text, chat_id=42):
        self.message = _Msg(text)

        class _Chat:
            id = chat_id
        self.effective_chat = _Chat()


class _Ctx:
    bot = _Bot()


def test_message_handler_replies_and_splits(monkeypatch):
    # Force a very long backend answer -> handler sends multiple chunks.
    long_answer = "para " + "y" * 9000
    monkeypatch.setattr(
        "app.services.telegram.handlers.answer_question",
        lambda *a, **k: _async(long_answer),
    )
    upd = _Update("what are the warnings for ibuprofen?")
    asyncio.run(message_handler(upd, _Ctx()))
    assert len(upd.message.replies) >= 2
    assert all(len(r) <= TELEGRAM_LIMIT for r in upd.message.replies)


def test_message_handler_inflight_guard():
    """A second message while one is in flight gets a friendly 'one moment'."""
    from app.services.telegram import handlers
    handlers._inflight.add("42")
    try:
        upd = _Update("another question", chat_id=42)
        asyncio.run(message_handler(upd, _Ctx()))
        assert len(upd.message.replies) == 1
        assert "one moment" in upd.message.replies[0].lower()
    finally:
        handlers._inflight.discard("42")


def test_start_and_help_text():
    assert "leaflet" in WELCOME.lower() and "not medical advice" in WELCOME.lower()
    assert "how to use" in HELP.lower() and "ibuprofen" in HELP.lower()


async def _async(v):
    return v
