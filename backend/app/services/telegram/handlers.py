"""
Telegram command + message handlers.  [PRD v3.0 §9.2, M7]

Kept free of the python-telegram-bot import so the message-processing logic
(`answer_question`) is unit-testable with a mocked backend. `bot.py` wires these
into an Application.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

DISCLAIMER = ("\n\n_Informational only, sourced from FDA labels — not medical "
              "advice. Consult a healthcare professional._")

WELCOME = (
    "👋 *FDA Drug Information Assistant*\n\n"
    "Ask me about an FDA-approved drug — indications, warnings, dosage, adverse "
    "reactions, contraindications, or interactions. I answer only from official "
    "FDA label text, with citations, and I refuse when the labels don't cover it."
    + DISCLAIMER
)

HELP = (
    "*How to use me*\n\n"
    "Just send a question, e.g.:\n"
    "• What are the warnings for ibuprofen?\n"
    "• What is the dosage for amoxicillin?\n"
    "• Does warfarin interact with aspirin?\n\n"
    "Commands: /start · /help" + DISCLAIMER
)


def _backend_url() -> str:
    return os.environ.get("BACKEND_URL", "http://localhost:8000")


def _format_answer(data: dict) -> str:
    """Render the backend /ask-agentic payload as a Telegram message."""
    answer = (data.get("answer") or "").strip() or "I couldn't produce an answer."
    citations = data.get("citations") or []
    if citations:
        lines = ["\n\n*Sources:*"]
        seen = set()
        for c in citations:
            key = f"{c.get('source','')}#{c.get('section','')}"
            if key in seen:
                continue
            seen.add(key)
            title = c.get("section_title") or c.get("section", "")
            lines.append(f"{c.get('marker','')} {c.get('source','')} — {title}")
        answer += "\n".join(lines)
    return answer


async def answer_question(text: str, *, session_id: str | None = None,
                          client: httpx.AsyncClient | None = None) -> str:
    """Forward a question to the backend agentic endpoint; return a reply string.

    Async + error-handled (course requirement): on any backend error/timeout,
    returns a graceful failure message rather than raising, so the bot never
    crashes on a bad request.
    """
    payload = {"question": text, "session_id": session_id}
    url = f"{_backend_url()}/ask-agentic"
    own = client is None
    client = client or httpx.AsyncClient(timeout=120.0)
    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return _format_answer(resp.json())
    except Exception as e:  # noqa: BLE001 - degrade gracefully, never crash
        logger.warning("telegram backend call failed: %s", e)
        return ("Sorry — I couldn't reach the drug-information service just now. "
                "Please try again in a moment." + DISCLAIMER)


# --------------------------------------------------------------- PTB handlers
async def start_command(update, context) -> None:  # pragma: no cover - thin glue
    """/start — welcome + usage + disclaimer."""
    await update.message.reply_text(WELCOME, parse_mode="Markdown")


async def help_command(update, context) -> None:  # pragma: no cover - thin glue
    """/help — usage examples + disclaimer."""
    await update.message.reply_text(HELP, parse_mode="Markdown")


async def message_handler(update, context) -> None:  # pragma: no cover - thin glue
    """On a text message: forward to the agentic endpoint and reply."""
    text = (update.message.text or "").strip()
    if not text:
        return
    chat_id = str(update.effective_chat.id) if update.effective_chat else None
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = await answer_question(text, session_id=f"tg-{chat_id}" if chat_id else None)
    await update.message.reply_text(reply, parse_mode="Markdown")
