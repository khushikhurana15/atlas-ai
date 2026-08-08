"""
This file actually runs the bot.

Render's free tier only supports "Web Services" (which must listen
on a port), not "Background Workers" (which cost money). So we run a
tiny HTTP server in a background thread just to satisfy that
requirement - it doesn't do anything except respond "OK" - while the
actual bot logic (Telegram polling) runs exactly as before.

Run karne ke liye (project root se):
    python -m app.main
"""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
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


class _HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Atlas bot is running")

    def log_message(self, format, *args):
        pass  # keep the logs clean - we don't need every ping logged


def _run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), _HealthCheckHandler)
    server.serve_forever()


async def _on_startup(app):
    start_scheduler(app.bot)
    print("Daily brief scheduler started.")


def main():
    threading.Thread(target=_run_health_server, daemon=True).start()

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