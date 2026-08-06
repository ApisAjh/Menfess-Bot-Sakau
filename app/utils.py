"""
Fungsi-fungsi utilitas: logging, formatting caption, dan helper callback_data.
"""
import logging
from typing import Optional, Tuple

MEDIA_LABELS = {
    "text": "Text",
    "photo": "Photo",
    "video": "Video",
    "animation": "Animation",
    "audio": "Audio",
    "voice": "Voice",
    "sticker": "Sticker",
    "document": "Document",
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Redam log verbose dari httpx / telegram
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)


def build_admin_caption(media_type: str, content_preview: Optional[str]) -> str:
    """Format pesan yang dikirim ke admin (tanpa menampilkan identitas pengirim)."""
    label = MEDIA_LABELS.get(media_type, media_type.title())
    preview = content_preview if content_preview else "(tanpa teks)"
    return (
        "📩 Menfess Baru\n\n"
        f"Jenis:\n{label}\n\n"
        f"Isi:\n{preview}\n\n"
        "──────────────\n\n"
        "Pengirim:\nAnonymous"
    )


def build_channel_caption(text: Optional[str]) -> str:
    """Format pesan yang dipublish ke channel."""
    if text:
        return f"📩 Menfess\n\n{text}"
    return "📩 Menfess"


def make_callback_data(action: str, menfess_id: str) -> str:
    return f"{action}:{menfess_id}"


def parse_callback_data(data: str) -> Tuple[str, str]:
    action, _, menfess_id = data.partition(":")
    return action, menfess_id
