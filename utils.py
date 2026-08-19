"""Yordamchi funksiyalar: vaqt formati va matn tayyorlash."""
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from config import DATETIME_FMT

# Toshkent vaqti (UTC+5) — SQLite datetime('now') UTC da saqlaydi
TZ = timezone(timedelta(hours=5))
DB_DEADLINE_FMT = "%Y-%m-%d %H:%M"
SQLITE_FMT = "%Y-%m-%d %H:%M:%S"
NO_DEADLINE_WORDS = {"-", "yoq", "yo'q", "yo`q", "skip"}


def esc(value: Optional[str]) -> str:
    """HTML uchun xavfsiz matn."""
    return escape(value or "", quote=False)


def now_local() -> datetime:
    return datetime.now(TZ)


def from_sqlite(value: str) -> datetime:
    """SQLite dagi UTC vaqtni mahalliy vaqtga o'giradi."""
    return datetime.strptime(value, SQLITE_FMT).replace(tzinfo=timezone.utc).astimezone(TZ)


def parse_deadline(text: str) -> Optional[str]:
    """Foydalanuvchi kiritgan muddatni bazaga yoziladigan ko'rinishga o'giradi.

    ValueError — format noto'g'ri bo'lsa.
    """
    text = text.strip()
    if text.lower() in NO_DEADLINE_WORDS:
        return None
    dt = datetime.strptime(text, DATETIME_FMT)  # ValueError chiqishi mumkin
    return dt.strftime(DB_DEADLINE_FMT)


def deadline_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.strptime(value, DB_DEADLINE_FMT).replace(tzinfo=TZ)


def fmt_deadline(value: Optional[str]) -> str:
    dt = deadline_dt(value)
    return dt.strftime(DATETIME_FMT) if dt else "muddatsiz"


def fmt_submitted(value: str) -> str:
    return from_sqlite(value).strftime(DATETIME_FMT)


def is_expired(deadline: Optional[str]) -> bool:
    dt = deadline_dt(deadline)
    return dt is not None and now_local() > dt


def is_late(submitted_at: str, deadline: Optional[str]) -> bool:
    dt = deadline_dt(deadline)
    return dt is not None and from_sqlite(submitted_at) > dt


def shorten(text: str, limit: int = 30) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"
