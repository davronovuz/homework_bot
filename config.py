"""Bot sozlamalari (.env fayldan o'qiladi)."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
DB_PATH: Path = Path(os.getenv("DB_PATH") or (BASE_DIR / "homework.db"))

# Vaqt formati: 25.12.2026 18:00
DATETIME_FMT = "%d.%m.%Y %H:%M"


def check_config() -> None:
    """Bot ishga tushishidan oldin sozlamalarni tekshiradi."""
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylini yarating va BOT_TOKEN=... ni qo'shing "
            "(.env.example dan nusxa oling)."
        )
