"""
Konfigurasi environment untuk Menfess Bot.
Membaca variabel dari file .env (lokal) atau Environment Variables (Vercel).
"""
import logging
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("menfess_bot.config")


class ConfigError(Exception):
    """Error yang dilempar jika konfigurasi tidak valid."""


def _parse_admin_ids(raw: str) -> List[int]:
    ids: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.append(int(part))
        except ValueError:
            raise ConfigError(f"ADMIN_IDS tidak valid: '{part}' bukan angka.") from None
    if not ids:
        raise ConfigError("ADMIN_IDS tidak boleh kosong.")
    return ids


class Settings:
    """Menyimpan seluruh konfigurasi bot yang dibaca dari environment."""

    def __init__(self) -> None:
        self.bot_token: str = self._require("BOT_TOKEN")
        self.admin_ids: List[int] = _parse_admin_ids(self._require("ADMIN_IDS"))
        self.channel_id: int = int(self._require("CHANNEL_ID"))
        self.webhook_url: str = self._require("WEBHOOK_URL")
        self.webhook_secret: str = self._require("WEBHOOK_SECRET")

    @staticmethod
    def _require(key: str) -> str:
        value = os.getenv(key)
        if not value:
            raise ConfigError(f"Environment variable '{key}' wajib diisi di .env")
        return value


try:
    settings = Settings()
except ConfigError as exc:
    logger.error("Gagal memuat konfigurasi: %s", exc)
    raise
