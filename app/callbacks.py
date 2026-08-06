"""
Handler untuk callback query (tombol Publish / Delete) dari admin.
"""
import logging

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.config import settings
from app.services import MenfessEntry, clear_admin_keyboards, publish_to_channel, store
from app.utils import parse_callback_data

logger = logging.getLogger("menfess_bot.callbacks")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None or query.from_user is None:
        return

    admin_id = query.from_user.id
    if admin_id not in settings.admin_ids:
        await query.answer("⛔ Anda tidak memiliki akses.", show_alert=True)
        return

    action, menfess_id = parse_callback_data(query.data or "")
    entry = store.get(menfess_id)

    if entry is None:
        await query.answer("⚠️ Menfess tidak ditemukan (mungkin sudah kedaluwarsa).", show_alert=True)
        return

    if entry.status != "pending":
        await query.answer("⚠️ Menfess ini sudah diproses oleh admin lain.", show_alert=True)
        try:
            await query.edit_message_reply_markup(reply_markup=None)
        except TelegramError:
            pass
        return

    if action == "publish":
        await _handle_publish(context, menfess_id, entry)
        await query.answer("✅ Menfess dipublikasikan.")
    elif action == "delete":
        await _handle_delete(context, menfess_id, entry)
        await query.answer("🗑 Menfess dihapus.")
    else:
        await query.answer("⚠️ Aksi tidak dikenal.", show_alert=True)


async def _handle_publish(context: ContextTypes.DEFAULT_TYPE, menfess_id: str, entry: MenfessEntry) -> None:
    bot = context.bot

    # Tandai lebih dulu untuk mengurangi risiko double-publish pada request beruntun.
    store.set_status(menfess_id, "published")

    try:
        await publish_to_channel(bot, entry)
    except TelegramError as exc:
        logger.error("Gagal publish menfess %s ke channel: %s", menfess_id, exc)
        store.set_status(menfess_id, "pending")  # rollback agar bisa dicoba ulang
        try:
            await bot.send_message(
                chat_id=entry.user_chat_id,
                text="⚠️ Terjadi kesalahan saat mempublikasikan menfess Anda. Silakan hubungi admin.",
            )
        except TelegramError:
            pass
        return

    await clear_admin_keyboards(bot, entry, "✅ Menfess ini telah dipublikasikan.")

    try:
        await bot.send_message(chat_id=entry.user_chat_id, text="✅ Menfess Anda telah dipublikasikan.")
    except TelegramError as exc:
        logger.warning("Gagal mengirim notifikasi publish ke user %s: %s", entry.user_id, exc)


async def _handle_delete(context: ContextTypes.DEFAULT_TYPE, menfess_id: str, entry: MenfessEntry) -> None:
    bot = context.bot
    store.set_status(menfess_id, "deleted")
    await clear_admin_keyboards(bot, entry, "🗑 Menfess ini telah dihapus.")

    try:
        await bot.send_message(
            chat_id=entry.user_chat_id,
            text="❌ Maaf, menfess Anda tidak dipublikasikan.",
        )
    except TelegramError as exc:
        logger.warning("Gagal mengirim notifikasi delete ke user %s: %s", entry.user_id, exc)
