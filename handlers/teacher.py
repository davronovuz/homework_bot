"""O'qituvchi uchun handlerlar: guruh, vazifa, baholash."""
import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from db import queries
from filters import RoleFilter
from notify import safe_send
from states import Grading, NewAssignment, NewGroup
from utils import esc, fmt_deadline, fmt_submitted, is_late, parse_deadline

logger = logging.getLogger(__name__)

router = Router(name="teacher")
router.message.filter(RoleFilter("teacher"))
router.callback_query.filter(RoleFilter("teacher"))

MAX_LIST = 20


# ---------- menyu tugmalari (FSM handlerlaridan oldin ro'yxatdan o'tadi) ----------

@router.message(F.text == kb.BTN_NEW_GROUP)
async def new_group_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(NewGroup.name)
    await message.answer(
        "Guruh nomini yozing (masalan: <i>10-A matematika</i>):\n\n/bekor — bekor qilish",
        reply_markup=kb.remove_kb,
    )


@router.message(F.text == kb.BTN_MY_GROUPS)
async def my_groups(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    groups = await queries.teacher_groups(user["id"])
    if not groups:
        await message.answer("Sizda hali guruh yo'q. «➕ Guruh yaratish» tugmasini bosing.")
        return
    lines = ["<b>Guruhlaringiz:</b>"]
    for g in groups[:MAX_LIST]:
        lines.append(
            f"\n• <b>{esc(g['name'])}</b>\n  kod: <code>{g['code']}</code> · o'quvchilar: {g['students']}"
        )
    await message.answer("\n".join(lines))


@router.message(F.text == kb.BTN_NEW_ASSIGNMENT)
async def new_assignment_start(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    groups = await queries.teacher_groups(user["id"])
    if not groups:
        await message.answer("Avval guruh yarating: «➕ Guruh yaratish».")
        return
    await state.set_state(NewAssignment.group)
    await message.answer("Qaysi guruhga vazifa qo'shamiz?", reply_markup=kb.groups_kb(groups[:MAX_LIST]))


@router.message(F.text == kb.BTN_TEACHER_ASSIGNMENTS)
async def teacher_assignments(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    assignments = await queries.teacher_assignments(user["id"])
    if not assignments:
        await message.answer("Hali vazifa qo'shmagansiz. «📝 Vazifa qo'shish» tugmasini bosing.")
        return
    await message.answer(
        "<b>Vazifalaringiz</b> (batafsil ko'rish uchun bosing):",
        reply_markup=kb.assignments_kb(assignments[:MAX_LIST]),
    )


# ---------- guruh yaratish ----------

@router.message(NewGroup.name, F.text)
async def new_group_name(message: Message, state: FSMContext, user) -> None:
    name = " ".join(message.text.split())
    if not 2 <= len(name) <= 64:
        await message.answer("Guruh nomi 2 tadan 64 tagacha belgidan iborat bo'lsin. Qayta yozing:")
        return
    group = await queries.create_group(name, user["id"])
    await state.clear()
    await message.answer(
        f"✅ Guruh yaratildi: <b>{esc(group['name'])}</b>\n\n"
        f"Qo'shilish kodi: <code>{group['code']}</code>\n"
        "Shu kodni o'quvchilaringizga bering.",
        reply_markup=kb.main_menu("teacher"),
    )


@router.message(NewGroup.name)
async def new_group_name_invalid(message: Message) -> None:
    await message.answer("Guruh nomini matn ko'rinishida yozing.")


# ---------- guruhlar ro'yxati ----------

# ---------- vazifa qo'shish ----------

@router.callback_query(NewAssignment.group, kb.GroupCB.filter(F.action == "pick"))
async def new_assignment_group(
    call: CallbackQuery, callback_data: kb.GroupCB, state: FSMContext, user
) -> None:
    group = await queries.get_group(callback_data.group_id)
    if group is None or group["teacher_id"] != user["id"]:
        await call.answer("Guruh topilmadi.", show_alert=True)
        return
    await state.update_data(group_id=group["id"], group_name=group["name"])
    await state.set_state(NewAssignment.title)
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        f"Guruh: <b>{esc(group['name'])}</b>\n\nVazifa sarlavhasini yozing:\n\n/bekor — bekor qilish"
    )
    await call.answer()


@router.message(NewAssignment.title, F.text)
async def new_assignment_title(message: Message, state: FSMContext) -> None:
    title = " ".join(message.text.split())
    if not 3 <= len(title) <= 100:
        await message.answer("Sarlavha 3 tadan 100 tagacha belgi bo'lsin. Qayta yozing:")
        return
    await state.update_data(title=title)
    await state.set_state(NewAssignment.description)
    await message.answer("Vazifa matnini (izohini) yozing.\nIzoh kerak bo'lmasa «-» yuboring:")


@router.message(NewAssignment.description, F.text)
async def new_assignment_description(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    description = None if text == "-" else text[:2000]
    await state.update_data(description=description)
    await state.set_state(NewAssignment.deadline)
    await message.answer(
        "Topshirish muddatini yozing: <code>kk.oo.yyyy soat:daqiqa</code>\n"
        "Masalan: <code>25.12.2026 18:00</code>\n"
        "Muddat kerak bo'lmasa «-» yuboring:"
    )


@router.message(NewAssignment.deadline, F.text)
async def new_assignment_deadline(message: Message, state: FSMContext, bot: Bot, user) -> None:
    try:
        deadline = parse_deadline(message.text)
    except ValueError:
        await message.answer(
            "Format noto'g'ri. Namuna: <code>25.12.2026 18:00</code> yoki «-»."
        )
        return

    data = await state.get_data()
    group_id = data.get("group_id")
    group = await queries.get_group(group_id) if group_id else None
    if group is None or group["teacher_id"] != user["id"]:
        await state.clear()
        await message.answer("Guruh topilmadi, qaytadan boshlang.", reply_markup=kb.main_menu("teacher"))
        return

    assignment_id = await queries.create_assignment(
        group_id=group["id"], title=data["title"], description=data.get("description"), deadline=deadline
    )
    await state.clear()
    await message.answer(
        f"✅ Vazifa qo'shildi.\n\n<b>{esc(data['title'])}</b>\n"
        f"Guruh: {esc(group['name'])}\nMuddat: {fmt_deadline(deadline)}",
        reply_markup=kb.main_menu("teacher"),
    )

    students = await queries.group_students(group["id"])
    text = (
        f"📢 Yangi vazifa!\n\n<b>{esc(data['title'])}</b>\n"
        f"Guruh: {esc(group['name'])}\nMuddat: {fmt_deadline(deadline)}\n\n"
        "«📚 Vazifalar» bo'limidan ko'ring."
    )
    sent = 0
    for student in students:
        sent += await safe_send(bot, student["tg_id"], text)
    if students:
        await message.answer(f"🔔 {sent}/{len(students)} o'quvchiga xabar yuborildi.")


@router.message(NewAssignment.group)
async def new_assignment_group_invalid(message: Message) -> None:
    await message.answer("Yuqoridagi ro'yxatdan guruhni tanlang yoki /bekor ni bosing.")


@router.message(NewAssignment.title)
@router.message(NewAssignment.description)
@router.message(NewAssignment.deadline)
async def new_assignment_invalid(message: Message) -> None:
    await message.answer("Iltimos, matn yuboring yoki /bekor ni bosing.")


# ---------- vazifalar va baholash ----------

@router.callback_query(kb.AsgCB.filter(F.action == "view"))
async def view_assignment(call: CallbackQuery, callback_data: kb.AsgCB, user) -> None:
    assignment = await queries.get_assignment(callback_data.assignment_id)
    if assignment is None or assignment["teacher_id"] != user["id"]:
        await call.answer("Vazifa topilmadi.", show_alert=True)
        return
    submissions = await queries.assignment_submissions(assignment["id"])
    students = await queries.group_students(assignment["group_id"])
    text = (
        f"📝 <b>{esc(assignment['title'])}</b>\n"
        f"Guruh: {esc(assignment['group_name'])}\n"
        f"Muddat: {fmt_deadline(assignment['deadline'])}\n"
        f"Topshirganlar: {len(submissions)}/{len(students)}"
    )
    if assignment["description"]:
        text += f"\n\n{esc(assignment['description'])}"
    await call.message.answer(text, reply_markup=kb.assignment_actions_kb(assignment["id"], "teacher"))
    await call.answer()


@router.callback_query(kb.AsgCB.filter(F.action == "subs"))
async def view_submissions(call: CallbackQuery, callback_data: kb.AsgCB, user) -> None:
    assignment = await queries.get_assignment(callback_data.assignment_id)
    if assignment is None or assignment["teacher_id"] != user["id"]:
        await call.answer("Vazifa topilmadi.", show_alert=True)
        return
    submissions = await queries.assignment_submissions(assignment["id"])
    if not submissions:
        await call.answer("Hali hech kim topshirmagan.", show_alert=True)
        return
    await call.message.answer(
        f"📥 <b>{esc(assignment['title'])}</b> — javoblar:",
        reply_markup=kb.submissions_kb(submissions[:MAX_LIST]),
    )
    await call.answer()


@router.callback_query(kb.SubCB.filter(F.action == "view"))
async def view_submission(call: CallbackQuery, callback_data: kb.SubCB, user) -> None:
    sub = await queries.get_submission_by_id(callback_data.submission_id)
    if sub is None or sub["teacher_id"] != user["id"]:
        await call.answer("Javob topilmadi.", show_alert=True)
        return
    late = " ⚠️ kechikkan" if is_late(sub["submitted_at"], sub["deadline"]) else ""
    grade = f"{sub['grade']}" if sub["grade"] is not None else "qo'yilmagan"
    caption = (
        f"👤 <b>{esc(sub['student_name'])}</b>\n"
        f"Vazifa: {esc(sub['assignment_title'])}\n"
        f"Topshirildi: {fmt_submitted(sub['submitted_at'])}{late}\n"
        f"Baho: {grade}"
    )
    if sub["text"]:
        caption += f"\n\n<b>Javob:</b>\n{esc(sub['text'])}"
    await call.message.answer(caption, reply_markup=kb.grade_kb(sub["id"]))
    if sub["file_id"]:
        sender = {
            "photo": call.message.answer_photo,
            "document": call.message.answer_document,
            "video": call.message.answer_video,
            "audio": call.message.answer_audio,
            "voice": call.message.answer_voice,
        }.get(sub["file_type"], call.message.answer_document)
        try:
            await sender(sub["file_id"])
        except TelegramAPIError as error:
            logger.warning("Fayl yuborilmadi: %s", error)
            await call.message.answer("⚠️ Faylni yuborib bo'lmadi.")
    await call.answer()


@router.callback_query(kb.SubCB.filter(F.action == "grade"))
async def grade_start(call: CallbackQuery, callback_data: kb.SubCB, state: FSMContext, user) -> None:
    sub = await queries.get_submission_by_id(callback_data.submission_id)
    if sub is None or sub["teacher_id"] != user["id"]:
        await call.answer("Javob topilmadi.", show_alert=True)
        return
    await state.set_state(Grading.grade)
    await state.update_data(submission_id=sub["id"])
    await call.message.answer(
        f"<b>{esc(sub['student_name'])}</b> uchun baho yozing (1 dan 5 gacha):\n\n/bekor — bekor qilish"
    )
    await call.answer()


@router.message(Grading.grade, F.text)
async def grade_finish(message: Message, state: FSMContext, bot: Bot, user) -> None:
    text = message.text.strip()
    if not text.isdigit() or not 1 <= int(text) <= 5:
        await message.answer("Baho 1 dan 5 gacha butun son bo'lsin. Qayta yozing:")
        return
    grade = int(text)
    data = await state.get_data()
    sub = await queries.get_submission_by_id(data.get("submission_id", 0))
    if sub is None or sub["teacher_id"] != user["id"]:
        await state.clear()
        await message.answer("Javob topilmadi.", reply_markup=kb.main_menu("teacher"))
        return
    await queries.set_grade(sub["id"], grade)
    await state.clear()
    await message.answer(
        f"✅ <b>{esc(sub['student_name'])}</b> — baho: {grade}", reply_markup=kb.main_menu("teacher")
    )
    await safe_send(
        bot,
        sub["student_tg_id"],
        f"📊 «{esc(sub['assignment_title'])}» vazifangiz baholandi: <b>{grade}</b>",
    )


@router.message(Grading.grade)
async def grade_invalid(message: Message) -> None:
    await message.answer("Bahoni raqam bilan yozing (1-5).")
