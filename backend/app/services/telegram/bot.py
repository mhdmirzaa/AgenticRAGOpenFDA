"""
Telegram bot entry point.  [PRD v3.0 §9.2, M7]

Wires the command + message handlers into a python-telegram-bot Application and
long-polls. Degrades safely: with no TELEGRAM__BOT_TOKEN the bot logs and exits
cleanly (no crash loop), leaving the rest of the stack unaffected.

Run: `python -m app.services.telegram.bot`
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def get_token() -> str:
    """Read the bot token (course naming TELEGRAM__BOT_TOKEN; flat name too)."""
    from app.config import get_settings
    return (
        os.environ.get("TELEGRAM__BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or getattr(get_settings(), "telegram_bot_token", "")
        or ""
    ).strip()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    token = get_token()
    if not token:
        logger.warning(
            "TELEGRAM__BOT_TOKEN not set — Telegram bot disabled. "
            "The rest of the system is unaffected."
        )
        return 0

    try:
        from telegram.ext import (
            Application, CommandHandler, MessageHandler, filters,
        )
    except Exception as e:  # python-telegram-bot not installed
        logger.error("python-telegram-bot unavailable (%s); bot not started", e)
        return 0

    from app.services.telegram.handlers import (
        start_command, help_command, message_handler,
    )

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))

    logger.info("Telegram bot starting (long polling)…")
    app.run_polling()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
