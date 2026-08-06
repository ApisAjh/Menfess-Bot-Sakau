"""
Business logic: penyimpanan sementara (in-memory, tanpa database),
pengiriman menfess ke admin, dan publish ke channel.
"""
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.config import settings
from app.utils import build_admin_caption, build_channel_caption, make_callback_data

logger = logging.getLogger("menfess_bot.services")

# ---------------------------------------------------------------------------
# In-memory store (TANPA DATABASE)
#
# CATATAN PENTING:
# Bot ini didesain tanpa database dan berjalan di Vercel Serverless, sehingga
# state (status pending/published/deleted) disimpan di memori proses. Ini
# bekerja baik selama function tetap "warm" antar-request. Pada cold start,
# state sebelumnya bisa hilang, sehingga menfess yang sedang pending bisa
# gagal ditemukan saat tombol ditekan. Ini adalah trade-off yang disengaja
# sesuai requirement "tanpa database". Lihat bagian Troubleshooting di
# README untuk opsi upgrade ke storage ringan (mis. Vercel KV) bila
# dibutuhkan keandalan lebih tinggi di traffic besar.
# ---------------------------------------------------------------------------


@dataclass
class MenfessEntry:
    user_id: int
    user_chat_id: int
    media_type: str
    file_id: Optional[str]
    text: Optional[str]
    status: str = "pending"  # pending | published | deleted
    admin_messages: List[Tuple[int, int]] = field(default_factory=list)  # (admin_id, message_id)
    created_at: float = field(default_factory=time.time)


class MenfessStore:
    def __init__(self) -> None:
        self._data: Dict[str, MenfessEntry] = {}

    def create(self, menfess_id: str, entry: MenfessEntry) -> None:
        self._data[menfess_id] = entry

    def get(self, menfess_id: str) -> Optional[MenfessEntry]:
        return self._data.get(menfess_id)

    def add_admin_message(self, menfess_id: str, admin_id: int, message_id: int) -> None:
        entry = self._data.get(menfess_id)
        if entry:
            entry.admin_messages.append((admin_id, message_id))

    def set_status(self, menfess_id: str, status: str) -> None:
        entry = self._data.get(menfess_id)
        if entry:
            entry.status = status


store = MenfessStore()


def build_menfess_id(user_id: int, message_id: int) -> str:
    return f"{user_id}_{message_id}"


def extract_media(update_message) -> Tuple[str, Optional[str], Optional[str]]:
    """Mengembalikan (media_type, file_id, text_or_caption)."""
    if update_message.text:
        return "text", None, update_message.text
    if update_message.photo:
        return "photo", update_message.photo[-1].file_id, update_message.caption
    if update_message.video:
        return "video", update_message.video.file_id, update_message.caption
    if update_message.animation:
        return "animation", update_message.animation.file_id, update_message.caption
    if update_message.audio:
        return "audio", update_message.audio.file_id, update_message.caption
    if update_message.voice:
        return "voice", update_message.voice.file_id, update_message.caption
    if update_message.sticker:
        return "sticker", update_message.sticker.file_id, None
    if update_message.document:
        return "document", update_message.document.file_id, update_message.caption
    return "unsupported", None, None


def build_admin_keyboard(menfess_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📢 Publish", callback_data=make_callback_data("publish", menfess_id)),
                InlineKeyboardButton("🗑 Delete", callback_data=make_callback_data("delete", menfess_id)),
            ]
        ]
    )


async def _send_by_type(
    bot: Bot,
    chat_id: int,
    media_type: str,
    file_id: Optional[str],
    caption: Optional[str],
    reply_markup=None,
):
    """Kirim pesan sesuai jenis media, TANPA forward."""
    kwargs = {"chat_id": chat_id}
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup

    if media_type == "text":
        return await bot.send_message(text=caption or "", **kwargs)
    if media_type == "photo":
        return await bot.send_photo(photo=file_id, caption=caption, **kwargs)
    if media_type == "video":
        return await bot.send_video(video=file_id, caption=caption, **kwargs)
    if media_type == "animation":
        return await bot.send_animation(animation=file_id, caption=caption, **kwargs)
    if media_type == "audio":
        return await bot.send_audio(audio=file_id, caption=caption, **kwargs)
    if media_type == "voice":
        return await bot.send_voice(voice=file_id, caption=caption, **kwargs)
    if media_type == "sticker":
        # Sticker tidak mendukung caption di Telegram Bot API.
        return await bot.send_sticker(sticker=file_id, **kwargs)
    if media_type == "document":
        return await bot.send_document(document=file_id, caption=caption, **kwargs)
    raise ValueError(f"Jenis media tidak didukung: {media_type}")


async def forward_to_admins(bot: Bot, menfess_id: str, entry: MenfessEntry) -> None:
    """Kirim menfess ke seluruh admin dengan tombol Publish/Delete."""
    keyboard = build_admin_keyboard(menfess_id)
    admin_caption = build_admin_caption(entry.media_type, entry.text)

    for admin_id in settings.admin_ids:
        try:
            msg = await _send_by_type(
                bot,
                admin_id,
                entry.media_type,
                entry.file_id,
                admin_caption,
                reply_markup=keyboard,
            )
            store.add_admin_message(menfess_id, admin_id, msg.message_id)
        except TelegramError as exc:
            logger.error("Gagal mengirim menfess ke admin %s: %s", admin_id, exc)


async def publish_to_channel(bot: Bot, entry: MenfessEntry) -> None:
    """Publish menfess ke channel tujuan, tanpa identitas pengirim & tanpa forward."""
    if entry.media_type == "text":
        await bot.send_message(chat_id=settings.channel_id, text=build_channel_caption(entry.text))
        return

    caption = build_channel_caption(entry.text)
    await _send_by_type(bot, settings.channel_id, entry.media_type, entry.file_id, caption)


async def clear_admin_keyboards(bot: Bot, entry: MenfessEntry, note: str) -> None:
    """Hapus inline keyboard di semua salinan pesan admin dan tambahkan catatan status."""
    for admin_id, message_id in entry.admin_messages:
        try:
            await bot.edit_message_reply_markup(chat_id=admin_id, message_id=message_id, reply_markup=None)
        except TelegramError as exc:
            logger.warning("Gagal mengubah keyboard admin %s: %s", admin_id, exc)
        try:
            await bot.send_message(chat_id=admin_id, text=note, reply_to_message_id=message_id)
        except TelegramError as exc:
            logger.warning("Gagal mengirim catatan status ke admin %s: %s", admin_id, exc)
