"""
Entry point Webhook untuk Vercel Serverless.
Menerima update dari Telegram, memprosesnya via python-telegram-bot,
lalu mengembalikan response secepat mungkin.
"""
import logging
import sys
from pathlib import Path

# Pastikan folder root project ada di sys.path agar `app.*` bisa di-import
# saat dijalankan sebagai Vercel Serverless Function.
sys.path.append(str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request, Response, status
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from app.callbacks import callback_handler
from app.config import settings
from app.handlers import menfess_handler, start_handler
from app.utils import setup_logging

setup_logging()
logger = logging.getLogger("menfess_bot.webhook")

app = FastAPI(title="Menfess Bot Webhook")

telegram_app: Application = Application.builder().token(settings.bot_token).build()

telegram_app.add_handler(CommandHandler("start", start_handler))
telegram_app.add_handler(
    MessageHandler(
        (
            filters.TEXT
            | filters.PHOTO
            | filters.VIDEO
            | filters.ANIMATION
            | filters.AUDIO
            | filters.VOICE
            | filters.Sticker.ALL
            | filters.Document.ALL
        )
        & ~filters.COMMAND,
        menfess_handler,
    )
)
telegram_app.add_handler(CallbackQueryHandler(callback_handler))

_initialized = False


async def _ensure_initialized() -> None:
    global _initialized
    if not _initialized:
        await telegram_app.initialize()
        _initialized = True


@app.get("/api/webhook")
async def health_check() -> dict:
    return {"status": "ok", "service": "menfess-bot"}


@app.post("/api/webhook")
async def telegram_webhook(request: Request) -> Response:
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret_header != settings.webhook_secret:
        logger.warning("Webhook secret tidak valid.")
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    try:
        data = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("Gagal parsing body webhook: %s", exc)
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    await _ensure_initialized()

    try:
        update = Update.de_json(data, telegram_app.bot)
        await telegram_app.process_update(update)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gagal memproses update: %s", exc)
        # Tetap kembalikan 200 agar Telegram tidak melakukan retry berulang
        # untuk error yang berasal dari logic internal kita.
        return Response(status_code=status.HTTP_200_OK)

    return Response(status_code=status.HTTP_200_OK)
