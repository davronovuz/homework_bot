"""Uchidan-uchiga smoke test: soxta Telegram API bilan to'liq stsenariy.

Ishga tushirish:  python tests/smoke_test.py
"""
import asyncio
import itertools
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Konfiguratsiya import qilinishidan oldin sozlanadi
_tmp_db = Path(tempfile.mkdtemp()) / "test.db"
os.environ["BOT_TOKEN"] = "123456:TEST"
os.environ["DB_PATH"] = str(_tmp_db)

from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.types import (  # noqa: E402
    CallbackQuery,
    Chat,
    Document,
    Message,
    Update,
    User,
)

from config import DATETIME_FMT  # noqa: E402
from db import close_db, init_db  # noqa: E402
from db import queries  # noqa: E402
from handlers import setup_routers  # noqa: E402
from middlewares import UserMiddleware  # noqa: E402

_ids = itertools.count(1000)


class MockedSession(BaseSession):
    """API chaqiruvlarini yozib boradi va soxta javob qaytaradi."""

    def __init__(self) -> None:
        super().__init__()
        self.sent: list[str] = []
        self.calls: list[str] = []

    async def close(self) -> None:
        pass

    async def stream_content(self, *args, **kwargs):  # pragma: no cover
        yield b""

    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        self.calls.append(name)
        if name in ("SendMessage", "SendPhoto", "SendDocument"):
            text = getattr(method, "text", None) or getattr(method, "caption", None) or f"<{name}>"
            self.sent.append(f"[{method.chat_id}] {text}")
        if name == "GetMe":
            return User(id=1, is_bot=True, first_name="Bot", username="test_bot")
        returning = getattr(type(method), "__returning__", bool)
        if returning is bool or "bool" in str(returning) and "Message" not in str(returning):
            return True
        if "Message" in str(returning):
            return _make_message(bot, chat_id=getattr(method, "chat_id", 1), text=getattr(method, "text", ""))
        return True

    def last(self, n: int = 1) -> str:
        return "\n".join(self.sent[-n:])


def _make_message(bot, chat_id: int, text: str = "", **kwargs) -> Message:
    user = User(id=chat_id, is_bot=False, first_name="U")
    msg = Message(
        message_id=next(_ids),
        date=datetime.now(),
        chat=Chat(id=chat_id, type="private"),
        from_user=user,
        text=text or None,
        **kwargs,
    )
    return msg.as_(bot)


async def send(dp: Dispatcher, bot: Bot, tg_id: int, text: str, **kwargs) -> None:
    message = _make_message(bot, tg_id, text, **kwargs)
    await dp.feed_update(bot, Update(update_id=next(_ids), message=message))


async def press(dp: Dispatcher, bot: Bot, tg_id: int, data: str) -> None:
    message = _make_message(bot, tg_id, "menu")
    call = CallbackQuery(
        id=str(next(_ids)),
        from_user=User(id=tg_id, is_bot=False, first_name="U"),
        chat_instance="ci",
        message=message,
        data=data,
    )
    await dp.feed_update(bot, Update(update_id=next(_ids), callback_query=call))


def check(condition: bool, label: str) -> None:
    print(("  ✅ " if condition else "  ❌ ") + label)
    if not condition:
        raise AssertionError(label)


async def main() -> None:
    await init_db()
    session = MockedSession()
    bot = Bot(token="123456:TEST", session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(UserMiddleware())
    dp.include_router(setup_routers())

    TEACHER, STUDENT = 111, 222

    print("1) Ro'yxatdan o'tish")
    await send(dp, bot, TEACHER, "/start")
    check("Ismingiz" in session.last(), "ism so'raldi")
    await send(dp, bot, TEACHER, "A")
    check("64 tagacha" in session.last(), "qisqa ism rad etildi")
    await send(dp, bot, TEACHER, "Ali Valiyev")
    check("Rolingizni tanlang" in session.last(), "rol so'raldi")
    await send(dp, bot, TEACHER, "o'qituvchi")
    check("tugmalar orqali" in session.last(), "rol holatida matn boshi berk ko'cha emas")
    await press(dp, bot, TEACHER, "role:teacher")
    teacher = await queries.get_user(TEACHER)
    check(teacher is not None and teacher["role"] == "teacher", "o'qituvchi bazaga yozildi")

    await send(dp, bot, STUDENT, "/start")
    await send(dp, bot, STUDENT, "Olim Karimov")
    await press(dp, bot, STUDENT, "role:student")
    student = await queries.get_user(STUDENT)
    check(student is not None and student["role"] == "student", "o'quvchi bazaga yozildi")

    print("2) Guruh yaratish va qo'shilish")
    await send(dp, bot, TEACHER, "➕ Guruh yaratish")
    await send(dp, bot, TEACHER, "10-A matematika")
    groups = await queries.teacher_groups(teacher["id"])
    check(len(groups) == 1, "guruh yaratildi")
    code = groups[0]["code"]
    check(code in session.last(), "kod xabarda ko'rsatildi")

    await send(dp, bot, STUDENT, "🔑 Guruhga qo'shilish")
    await send(dp, bot, STUDENT, "XXXXXX")
    check("topilmadi" in session.last(), "noto'g'ri kod rad etildi")
    await send(dp, bot, STUDENT, code.lower())  # kichik harf ham ishlashi kerak
    check(await queries.is_member(groups[0]["id"], student["id"]), "o'quvchi guruhga qo'shildi")
    check(any(str(TEACHER) in s and "qo'shildi" in s for s in session.sent[-3:]), "o'qituvchiga xabar ketdi")

    await send(dp, bot, STUDENT, "🔑 Guruhga qo'shilish")
    await send(dp, bot, STUDENT, code)
    check("allaqachon" in session.last(), "takroriy qo'shilish to'xtatildi")

    print("3) Vazifa qo'shish")
    await send(dp, bot, TEACHER, "📝 Vazifa qo'shish")
    await press(dp, bot, TEACHER, f"grp:pick:{groups[0]['id']}")
    await send(dp, bot, TEACHER, "Uy vazifasi 1")
    await send(dp, bot, TEACHER, "5-mashq, 12-bet")
    await send(dp, bot, TEACHER, "notogri format")
    check("Format noto'g'ri" in session.last(), "noto'g'ri sana rad etildi")
    deadline = (datetime.now() + timedelta(days=3)).strftime(DATETIME_FMT)
    await send(dp, bot, TEACHER, deadline)
    assignments = await queries.teacher_assignments(teacher["id"])
    check(len(assignments) == 1, "vazifa yaratildi")
    check(any(str(STUDENT) in s and "Yangi vazifa" in s for s in session.sent[-4:]), "o'quvchiga e'lon ketdi")
    asg_id = assignments[0]["id"]

    print("4) Topshirish")
    await send(dp, bot, STUDENT, "📚 Vazifalar")
    check("Vazifalaringiz" in session.last(), "vazifalar ro'yxati chiqdi")
    await press(dp, bot, STUDENT, f"asg:view:{asg_id}")
    check("Uy vazifasi 1" in session.last(), "vazifa tafsiloti chiqdi")
    await press(dp, bot, STUDENT, f"asg:submit:{asg_id}")
    await send(dp, bot, STUDENT, "Javobim: 5-mashq bajarildi")
    sub = await queries.get_submission(asg_id, student["id"])
    check(sub is not None and sub["text"].startswith("Javobim"), "javob saqlandi")
    check(any(str(TEACHER) in s and "topshirdi" in s for s in session.sent[-3:]), "o'qituvchiga xabar ketdi")

    print("5) Qayta topshirish (fayl bilan)")
    await press(dp, bot, STUDENT, f"asg:submit:{asg_id}")
    await send(
        dp, bot, STUDENT, "", document=Document(file_id="FILE123", file_unique_id="u1", file_name="uy.pdf")
    )
    sub = await queries.get_submission(asg_id, student["id"])
    check(sub["file_id"] == "FILE123" and sub["file_type"] == "document", "fayl javobi saqlandi")

    print("6) Baholash")
    await send(dp, bot, TEACHER, "📋 Vazifalarim")
    await press(dp, bot, TEACHER, f"asg:view:{asg_id}")
    check("Topshirganlar: 1/1" in session.last(), "topshirish statistikasi to'g'ri")
    await press(dp, bot, TEACHER, f"asg:subs:{asg_id}")
    await press(dp, bot, TEACHER, f"sub:view:{sub['id']}")
    check("Olim Karimov" in session.last(2), "javob ko'rsatildi")
    await press(dp, bot, TEACHER, f"sub:grade:{sub['id']}")
    await send(dp, bot, TEACHER, "9")
    check("1 dan 5 gacha" in session.last(), "noto'g'ri baho rad etildi")
    await send(dp, bot, TEACHER, "5")
    sub = await queries.get_submission(asg_id, student["id"])
    check(sub["grade"] == 5, "baho saqlandi")
    check(any(str(STUDENT) in s and "baholandi" in s for s in session.sent[-2:]), "o'quvchiga xabar ketdi")

    await send(dp, bot, STUDENT, "📊 Baholarim")
    check("O'rtacha ball" in session.last(), "baholar ro'yxati chiqdi")

    print("7) Xavfsizlik va chegaralar")
    other_group = await queries.create_group("Begona guruh", teacher["id"])
    await press(dp, bot, STUDENT, f"grp:pick:{other_group['id']}")  # o'quvchida bunday tugma yo'q
    check(session.calls[-1] == "AnswerCallbackQuery", "begona callback e'tiborsiz qoldirildi")
    check(await queries.is_member(other_group["id"], student["id"]) is False, "begona guruhga qo'shilmadi")

    # FSM ichida menyu tugmasi bosilsa, u ma'lumot sifatida saqlanmasligi kerak
    await send(dp, bot, TEACHER, "➕ Guruh yaratish")
    await send(dp, bot, TEACHER, "📋 Vazifalarim")
    check("Vazifalaringiz" in session.last(), "FSM ichida menyu tugmasi ishladi")
    check(len(await queries.teacher_groups(teacher["id"])) == 2, "tugma nomi guruh nomi sifatida saqlanmadi")

    # guruh tanlash bosqichida matn yozilsa yo'l ko'rsatiladi
    await send(dp, bot, TEACHER, "📝 Vazifa qo'shish")
    await send(dp, bot, TEACHER, "birinchi guruh")
    check("ro'yxatdan guruhni tanlang" in session.last(), "guruh tanlash bosqichi boshi berk ko'cha emas")
    await send(dp, bot, TEACHER, "/bekor")
    await send(dp, bot, STUDENT, "tasodifiy matn")
    check("Tushunmadim" in session.last(), "noma'lum xabarga javob bor")
    await send(dp, bot, TEACHER, "/bekor")
    check("Bekor qiladigan amal yo'q" in session.last(), "bo'sh bekor qilish to'g'ri")
    await send(dp, bot, TEACHER, "📝 Vazifa qo'shish")
    await send(dp, bot, TEACHER, "/bekor")
    check("bekor qilindi" in session.last(), "FSM bekor qilindi")

    # boshqa o'qituvchining javobini ko'rmaslik
    await queries.create_user(333, "Begona O'qituvchi", None, "teacher")
    await press(dp, bot, 333, f"sub:view:{sub['id']}")
    check(session.calls[-1] == "AnswerCallbackQuery", "begona o'qituvchiga javob berilmadi")

    await close_db()
    await bot.session.close()
    print(f"\n✅ Hammasi o'tdi. Jami {len(session.calls)} ta API chaqiruvi.")


if __name__ == "__main__":
    asyncio.run(main())
