"""
Telegram command + message handlers.  [PRD v3.0 §9.2, M7; hardened telegram-verify]

Kept free of the python-telegram-bot import so the message-processing logic
(`answer_question`, `split_message`) is unit-testable with a mocked backend.
`bot.py` wires these into an Application.

The bot is a THIN client: it forwards every question to the backend `/ask-agentic`
endpoint, so it goes through the SAME agentic pipeline (guardrail → route → scope →
retrieve → grade → decide → generate/refuse) and inherits the guardrail + rate
limiting — it never bypasses them.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

# Telegram's hard message limit is 4096 chars; leave margin for safety.
TELEGRAM_LIMIT = 4000

_DISCLAIMER_MD = ("\n\n_Informational only, sourced from FDA labels — not medical "
                  "advice. Consult a healthcare professional._")
_DISCLAIMER_PLAIN = ("\n\nInformational only, sourced from FDA labels — not medical "
                     "advice. Consult a healthcare professional.")

WELCOME = (
    "👋 *Leaflet — FDA Drug Companion*\n\n"
    "Ask me about an FDA-approved drug — indications, warnings, dosage, adverse "
    "reactions, contraindications, or interactions. I answer only from official "
    "FDA label text, with sources, and I say so honestly when the labels don't "
    "cover it." + _DISCLAIMER_MD
)

HELP = (
    "*How to use me*\n\n"
    "Just send a question, e.g.:\n"
    "• What are the warnings for ibuprofen?\n"
    "• What is the dosage for amoxicillin?\n"
    "• Does warfarin interact with aspirin?\n\n"
    "Commands: /start · /help" + _DISCLAIMER_MD
)


def _backend_url() -> str:
    return os.environ.get("BACKEND_URL", "http://localhost:8000")


def _format_answer(data: dict) -> str:
    """Render the /ask-agentic payload as a PLAIN-text Telegram message.

    Plain text (not Markdown) so arbitrary FDA-label content + `[n]` citation
    markers can never break Telegram's Markdown parser or be used to inject
    formatting. The answer already ends with the medical disclaimer (from the
    generation prompt); a compact Sources list is appended from the citations.
    """
    answer = (data.get("answer") or "").strip() or "I couldn't find an answer for that."
    citations = data.get("citations") or []
    if citations:
        lines = ["", "", "Sources:"]
        seen: set[str] = set()
        for c in citations:
            key = f"{c.get('source', '')}#{c.get('section', '')}"
            if key in seen:
                continue
            seen.add(key)
            title = c.get("section_title") or c.get("section", "")
            lines.append(f"{c.get('marker', '')} {c.get('source', '')} — {title}")
        answer += "\n".join(lines)
    return answer


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Split a long reply into Telegram-sized chunks on line boundaries.

    Keeps citations intact (they're inline `[n]` markers + a trailing Sources
    block) by never breaking mid-line unless a single line itself exceeds the
    limit (then it's hard-split). Returns [text] when it already fits.
    """
    if len(text) <= limit:
        return [text]
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(line), limit):
                chunks.append(line[i:i + limit])
            continue
        if current and len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


async def answer_question(text: str, *, session_id: str | None = None,
                          client: httpx.AsyncClient | None = None) -> str:
    """Forward a question to the backend agentic endpoint; return a reply string.

    Async + error-handled: on any backend error/timeout, returns a graceful
    failure message rather than raising, so the bot never crashes on a bad
    request. Presents the backend API key when configured (so it doesn't bypass
    auth/rate-limiting).
    """
    payload = {"question": text, "session_id": session_id}
    url = f"{_backend_url()}/ask-agentic"
    headers: dict[str, str] = {}
    api_key = os.environ.get("BACKEND_API_KEY", "")
    if api_key:
        headers["X-API-Key"] = api_key
    own = client is None
    client = client or httpx.AsyncClient(timeout=120.0)
    try:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        return _format_answer(resp.json())
    except Exception as e:  # noqa: BLE001 - degrade gracefully, never crash
        logger.warning("telegram backend call failed: %s", e)
        return ("Sorry — I couldn't reach the drug-information service just now. "
                "Please try again in a moment." + _DISCLAIMER_PLAIN)
    finally:
        if own:
            await client.aclose()


# --------------------------------------------------------------- PTB handlers
async def start_command(update, context) -> None:  # pragma: no cover - thin glue
    """/start — welcome + usage + disclaimer."""
    await update.message.reply_text(WELCOME, parse_mode="Markdown")


async def help_command(update, context) -> None:  # pragma: no cover - thin glue
    """/help — usage examples + disclaimer."""
    await update.message.reply_text(HELP, parse_mode="Markdown")


# Basic per-chat in-flight guard: one question at a time per chat, so a single
# user can't hammer the backend (the backend rate limit is the real limiter when
# AUTH/RATE are enabled; this serializes and gives friendly feedback).
_inflight: set[str] = set()


async def message_handler(update, context) -> None:
    """On a text message: forward to the agentic endpoint and reply (split if long)."""
    text = (update.message.text or "").strip()
    if not text:
        return
    chat = update.effective_chat.id if update.effective_chat else None
    chat_key = str(chat) if chat is not None else "unknown"

    if chat_key in _inflight:
        await update.message.reply_text(
            "Still working on your last question — one moment. 🌿")
        return

    _inflight.add(chat_key)
    try:
        if chat is not None:
            try:
                await context.bot.send_chat_action(chat_id=chat, action="typing")
            except Exception:  # noqa: BLE001 - typing indicator is best-effort
                pass
        reply = await answer_question(
            text, session_id=f"tg-{chat_key}" if chat is not None else None)
        # Plain text (no parse_mode) so label content can't break Markdown; split
        # long answers into multiple messages, preserving citations.
        for chunk in split_message(reply):
            await update.message.reply_text(chunk)
    finally:
        _inflight.discard(chat_key)
