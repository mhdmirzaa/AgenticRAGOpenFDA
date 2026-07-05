"""
Telegram bot service (secondary client).  [PRD v3.0 §9.2, M7]

Mirrors the course's Week-7 Telegram integration structure: command handlers
(/start, /help) + message processing that forwards a drug question to the
backend agentic endpoint (POST /ask-agentic) and replies with the cited answer
and the medical disclaimer. No RAG logic lives here — it is a thin, async,
error-handled messaging client, proving the backend is client-agnostic.

Configured via TELEGRAM__BOT_TOKEN (course naming; TELEGRAM_BOT_TOKEN also
accepted). Degrades safely: if the token is absent, the bot does not start and
the rest of the system is unaffected.
"""
