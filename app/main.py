"""
This file actually runs the bot.

Run karne ke liye (project root se):
    python -m app.main
"""

from telegram.ext import Application, CommandHandler, MessageHandler, filters
from app.config import TELEGRAM_BOT_TOKEN
from app.bot.handlers import (
    start_command,
    handle_text_message,
    handle_voice_message,
    handle_photo_message,
    handle_document_message,
)
from app.scheduler import start_scheduler


async def _on_startup(app):
    # post_init runs inside the bot's own asyncio event loop, which is
    # what AsyncIOScheduler needs - starting it any earlier (before
    # run_polling has a loop running) would fail.
    start_scheduler(app.bot)
    print("Daily brief scheduler started.")


def main():
    # concurrent_updates=True means one slow/stuck message can never
    # block other users (or other messages) from getting replies -
    # each update is processed independently.
    app = (
        Application.builder()
        .token(TELEGRAM_BOT_TOKEN)
        .concurrent_updates(True)
        .post_init(_on_startup)
        .build()
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document_message))

    print("Atlas bot is running... (press Ctrl+C to stop)")
    app.run_polling()


if __name__ == "__main__":
    main()