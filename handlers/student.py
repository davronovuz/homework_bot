"""O'quvchi uchun handlerlar: guruhga qo'shilish, vazifalar, topshirish."""
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import keyboards as kb
from db import queries
from filters import RoleFilter
from notify import safe_send
from states import JoinGroup, Submit
from utils import esc, fmt_deadline, fmt_submitted, is_expired, is_late

router = Router(name="student")
router.message.filter(RoleFilter("student"))
router.callback_query.filter(RoleFilter("student"))

MAX_LIST = 20


# ---------- menyu tugmalari (FSM handlerlaridan oldin ro'yxatdan o'tadi) ----------

@router.message(F.text == kb.BTN_MY_GROUPS)
async def my_groups(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    groups = await queries.student_groups(user["id"])
    if not groups:
        await message.answer("Siz hali guruhga qo'shilmagansiz. «🔑 Guruhga qo'shilish» tugmasini bosing.")
        return
    lines = ["<b>Guruhlaringiz:</b>"]
    for g in groups[:MAX_LIST]:
        lines.append(f"\n• <b>{esc(g['name'])}</b>\n  o'qituvchi: {esc(g['teacher_name'])}")
    await message.answer("\n".join(lines))


@router.message(F.text == kb.BTN_STUDENT_ASSIGNMENTS)
async def my_assignments(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    assignments = await queries.student_assignments(user["id"])
    if not assignments:
        await message.answer("Hozircha vazifa yo'q.")
        return
    marks = {}
    for a in assignments:
        if a["submission_id"] is None:
            marks[a["id"]] = "⏳ " if not is_expired(a["deadline"]) else "❗ "
        else:
            marks[a["id"]] = "✅ " if a["grade"] is None else f"[{a['grade']}] "
    await message.answer(
        "<b>Vazifalaringiz</b>\n⏳ topshirilmagan · ❗ muddati o'tgan · ✅ topshirilgan · [baho]",
        reply_markup=kb.assignments_kb(assignments[:MAX_LIST], marks=marks),
    )


@router.message(F.text == kb.BTN_MY_GRADES)
async def my_grades(message: Message, state: FSMContext, user) -> None:
    await state.clear()
    rows = await queries.student_grades(user["id"])
    if not rows:
        await message.answer("Hali baholangan vazifangiz yo'q.")
        return
    lines = ["<b>Baholaringiz:</b>"]
    for r in rows[:MAX_LIST]:
        lines.append(f"\n• {esc(r['title'])} ({esc(r['group_name'])}) — <b>{r['grade']}</b>")
    average = sum(r["grade"] for r in rows) / len(rows)
    lines.append(f"\n\n📊 O'rtacha ball: <b>{average:.2f}</b> ({len(rows)} ta baho)")
    await message.answer("\n".join(lines))


# ---------- guruhga qo'shilish ----------

@router.message(F.text == kb.BTN_JOIN_GROUP)
async def join_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(JoinGroup.code)
    await message.answer(
        "O'qituvchi bergan guruh kodini yozing (masalan: <code>A1B2C3</code>):\n\n/bekor — bekor qilish",
        reply_markup=kb.remove_kb,
    )


@router.message(JoinGroup.code, F.text)
async def join_code(message: Message, state: FSMContext, bot: Bot, user) -> None:
    code = message.text.strip().upper()
    group = await queries.get_group_by_code(code)
    if group is None:
        await message.answer("Bunday kodli guruh topilmadi. Kodni tekshirib, qayta yozing:")
        return
    joined = await queries.join_group(group["id"], user["id"])
    await state.clear()
    if not joined:
        await message.answer(
            f"Siz allaqachon <b>{esc(group['name'])}</b> guruhidasiz.",
            reply_markup=kb.main_menu("student"),
        )
        return
    await message.answer(
        f"✅ <b>{esc(group['name'])}</b> guruhiga qo'shildingiz!",
        reply_markup=kb.main_menu("student"),
    )
    teacher = await queries.get_user_by_id(group["teacher_id"])
    if teacher:
        await safe_send(
            bot,
            teacher["tg_id"],
            f"👤 <b>{esc(user['full_name'])}</b> «{esc(group['name'])}» guruhiga qo'shildi.",
        )


@router.message(JoinGroup.code)
async def join_code_invalid(message: Message) -> None:
    await message.answer("Kodni matn ko'rinishida yozing.")


# ---------- vazifalar ----------

@router.callback_query(kb.AsgCB.filter(F.action == "view"))
async def view_assignment(call: CallbackQuery, callback_data: kb.AsgCB, user) -> None:
    assignment = await queries.get_assignment(callback_data.assignment_id)
    if assignment is None or not await queries.is_member(assignment["group_id"], user["id"]):
        await call.answer("Vazifa topilmadi.", show_alert=True)
        return
    submission = await queries.get_submission(assignment["id"], user["id"])
    text = (
        f"📝 <b>{esc(assignment['title'])}</b>\n"
        f"Guruh: {esc(assignment['group_name'])}\n"
        f"Muddat: {fmt_deadline(assignment['deadline'])}"
    )
    if assignment["description"]:
        text += f"\n\n{esc(assignment['description'])}"
    if submission:
        late = " ⚠️ kechikib" if is_late(submission["submitted_at"], assignment["deadline"]) else ""
        grade = submission["grade"] if submission["grade"] is not None else "hali qo'yilmagan"
        text += f"\n\n✅ Topshirilgan: {fmt_submitted(submission['submitted_at'])}{late}\nBaho: {grade}"
    elif is_expired(assignment["deadline"]):
        text += "\n\n❗ Muddati o'tgan — topshirsangiz kechikkan deb belgilanadi."
    await call.message.answer(
        text,
        reply_markup=kb.assignment_actions_kb(
            assignment["id"], "student", submitted=submission is not None
        ),
    )
    await call.answer()


# ---------- topshirish ----------

@router.callback_query(kb.AsgCB.filter(F.action == "submit"))
async def submit_start(call: CallbackQuery, callback_data: kb.AsgCB, state: FSMContext, user) -> None:
    assignment = await queries.get_assignment(callback_data.assignment_id)
    if assignment is None or not await queries.is_member(assignment["group_id"], user["id"]):
        await call.answer("Vazifa topilmadi.", show_alert=True)
        return
    await state.set_state(Submit.content)
    await state.update_data(assignment_id=assignment["id"])
    await call.message.answer(
        f"«{esc(assignment['title'])}» uchun javobingizni yuboring.\n"
        "Matn, rasm, hujjat yoki ovozli xabar bo'lishi mumkin.\n\n/bekor — bekor qilish"
    )
    await call.answer()


@router.message(Submit.content)
async def submit_content(message: Message, state: FSMContext, bot: Bot, user) -> None:
    file_id = file_type = None
    if message.document:
        file_id, file_type = message.document.file_id, "document"
    elif message.photo:
        file_id, file_type = message.photo[-1].file_id, "photo"
    elif message.video:
        file_id, file_type = message.video.file_id, "video"
    elif message.audio:
        file_id, file_type = message.audio.file_id, "audio"
    elif message.voice:
        file_id, file_type = message.voice.file_id, "voice"

    text = message.text or message.caption
    if not text and not file_id:
        await message.answer("Javob sifatida matn yoki fayl yuboring.")
        return

    data = await state.get_data()
    assignment = await queries.get_assignment(data.get("assignment_id", 0))
    if assignment is None or not await queries.is_member(assignment["group_id"], user["id"]):
        await state.clear()
        await message.answer("Vazifa topilmadi.", reply_markup=kb.main_menu("student"))
        return

    submission = await queries.upsert_submission(
        assignment_id=assignment["id"],
        student_id=user["id"],
        text=text[:3000] if text else None,
        file_id=file_id,
        file_type=file_type,
    )
    await state.clear()
    late = " ⚠️ (kechikib)" if is_late(submission["submitted_at"], assignment["deadline"]) else ""
    await message.answer(
        f"✅ Javobingiz qabul qilindi{late}.\nVazifa: <b>{esc(assignment['title'])}</b>",
        reply_markup=kb.main_menu("student"),
    )
    teacher = await queries.get_user_by_id(assignment["teacher_id"])
    if teacher:
        await safe_send(
            bot,
            teacher["tg_id"],
            f"📥 <b>{esc(user['full_name'])}</b> «{esc(assignment['title'])}» vazifasini "
            f"topshirdi{late}.\n«📋 Vazifalarim» → javoblar bo'limidan ko'ring.",
        )
