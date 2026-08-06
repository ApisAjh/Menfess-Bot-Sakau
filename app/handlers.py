"""
Handler untuk pesan dari user (perintah /start dan menfess).
"""
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.services import MenfessEntry, build_menfess_id, extract_media, forward_to_admins, store

logger = logging.getLogger("menfess_bot.handlers")

CHANNEL_LINK = "https://t.me/iMenfessSakau"

WELCOME_TEXT = (
    "Halo {user}, selamat datang di MENFESS SAKAU BOT\n\n"
)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    name = user.first_name if user else "kamu"
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Official Channel", url=CHANNEL_LINK)]])
    await update.message.reply_text(WELCOME_TEXT.format(user=name), reply_markup=keyboard)


async def menfess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    media_type, file_id, text = extract_media(message)
    if media_type == "unsupported":
        await message.reply_text("⚠️ Jenis pesan ini belum didukung.")
        return

    menfess_id = build_menfess_id(user.id, message.message_id)
    entry = MenfessEntry(
        user_id=user.id,
        user_chat_id=message.chat_id,
        media_type=media_type,
        file_id=file_id,
        text=text,
    )
    store.create(menfess_id, entry)

    try:
        await forward_to_admins(context.bot, menfess_id, entry)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Gagal meneruskan menfess %s ke admin: %s", menfess_id, exc)
        await message.reply_text("⚠️ Terjadi kesalahan, silakan coba lagi nanti.")
        return

    await message.reply_text(
        "✅ Menfess berhasil dikirim.\n\nMohon tunggu hingga admin meninjau pesan Anda."
    )
