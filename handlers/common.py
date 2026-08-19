"""Ro'yxatdan o'tish, /start, /yordam va umumiy buyruqlar."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from db import queries
from states import Registration
from utils import esc

router = Router(name="common")
fallback_router = Router(name="fallback")

HELP_TEXT = (
    "<b>Uy vazifalari boti</b>\n\n"
    "O'qituvchi: guruh yaratadi, kodni o'quvchilarga beradi, vazifa qo'yadi va javoblarni baholaydi.\n"
    "O'quvchi: kod orqali guruhga qo'shiladi, vazifalarni ko'radi va javob yuboradi.\n\n"
    "Buyruqlar:\n"
    "/start — boshlash / menyu\n"
    "/yordam — shu yordam\n"
    "/bekor — joriy amalni bekor qilish"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    if user is not None:
        role_name = "o'qituvchi" if user["role"] == "teacher" else "o'quvchi"
        await message.answer(
            f"Xush kelibsiz, <b>{esc(user['full_name'])}</b>!\nRolingiz: {role_name}.",
            reply_markup=kb.main_menu(user["role"]),
        )
        return
    await state.set_state(Registration.full_name)
    await message.answer(
        "Assalomu alaykum! 👋\nUy vazifalari botiga xush kelibsiz.\n\n"
        "Ismingiz va familiyangizni yozing:",
        reply_markup=kb.remove_kb,
    )


@router.message(Command("yordam", "help"))
async def cmd_help(message: Message, user) -> None:
    markup = kb.main_menu(user["role"]) if user else None
    await message.answer(HELP_TEXT, reply_markup=markup)


@router.message(Command("bekor", "cancel"))
async def cmd_cancel(message: Message, state: FSMContext, user) -> None:
    if await state.get_state() is None:
        await message.answer("Bekor qiladigan amal yo'q.")
        return
    await state.clear()
    markup = kb.main_menu(user["role"]) if user else None
    await message.answer("Amal bekor qilindi.", reply_markup=markup)


@router.message(Registration.full_name, F.text)
async def reg_full_name(message: Message, state: FSMContext) -> None:
    full_name = " ".join(message.text.split())
    if len(full_name) < 3 or len(full_name) > 64:
        await message.answer("Ism-familiya 3 tadan 64 tagacha belgidan iborat bo'lsin. Qayta yozing:")
        return
    await state.update_data(full_name=full_name)
    await state.set_state(Registration.role)
    await message.answer("Rolingizni tanlang:", reply_markup=kb.role_kb())


@router.message(Registration.full_name)
async def reg_full_name_invalid(message: Message) -> None:
    await message.answer("Iltimos, ism-familiyangizni matn ko'rinishida yozing.")


@router.callback_query(Registration.role, kb.RoleCB.filter())
async def reg_role(call: CallbackQuery, callback_data: kb.RoleCB, state: FSMContext) -> None:
    data = await state.get_data()
    full_name = data.get("full_name")
    if not full_name:
        await state.clear()
        await call.message.answer("Xatolik yuz berdi. /start ni qayta bosing.")
        await call.answer()
        return
    role = callback_data.role
    user = await queries.create_user(
        tg_id=call.from_user.id,
        full_name=full_name,
        username=call.from_user.username,
        role=role,
    )
    await state.clear()
    await call.message.edit_reply_markup(reply_markup=None)
    if role == "teacher":
        text = (
            f"Tayyor, <b>{esc(user['full_name'])}</b>! Siz o'qituvchisiz. 👨‍🏫\n\n"
            "1. Guruh yarating\n2. Guruh kodini o'quvchilarga bering\n3. Vazifa qo'shing"
        )
    else:
        text = (
            f"Tayyor, <b>{esc(user['full_name'])}</b>! Siz o'quvchisiz. 🎓\n\n"
            "O'qituvchingizdan guruh kodini olib, «🔑 Guruhga qo'shilish» tugmasini bosing."
        )
    await call.message.answer(text, reply_markup=kb.main_menu(role))
    await call.answer()


@router.message(Registration.role)
async def reg_role_invalid(message: Message) -> None:
    await message.answer("Rolni quyidagi tugmalar orqali tanlang:", reply_markup=kb.role_kb())


@fallback_router.message(StateFilter(None))
async def unknown_message(message: Message, user) -> None:
    if user is None:
        await message.answer("Boshlash uchun /start ni bosing.")
        return
    await message.answer(
        "Tushunmadim. Quyidagi tugmalardan foydalaning yoki /yordam ni bosing.",
        reply_markup=kb.main_menu(user["role"]),
    )


@fallback_router.message()
async def unknown_in_state(message: Message) -> None:
    """FSM ichida kutilmagan xabar — boshi berk ko'cha bo'lmasligi uchun."""
    await message.answer("Iltimos, so'ralgan ma'lumotni yuboring yoki /bekor ni bosing.")


@fallback_router.callback_query()
async def stale_callback(call: CallbackQuery) -> None:
    await call.answer("Bu tugma eskirgan. Menyudan qaytadan boshlang.", show_alert=True)
