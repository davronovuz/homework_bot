"""Tugmalar (reply va inline)."""
from typing import Sequence

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from utils import shorten

# ---------- reply menyular ----------

BTN_NEW_GROUP = "➕ Guruh yaratish"
BTN_MY_GROUPS = "👥 Guruhlarim"
BTN_NEW_ASSIGNMENT = "📝 Vazifa qo'shish"
BTN_TEACHER_ASSIGNMENTS = "📋 Vazifalarim"
BTN_JOIN_GROUP = "🔑 Guruhga qo'shilish"
BTN_STUDENT_ASSIGNMENTS = "📚 Vazifalar"
BTN_MY_GRADES = "📊 Baholarim"

remove_kb = ReplyKeyboardRemove()


def main_menu(role: str) -> ReplyKeyboardMarkup:
    if role == "teacher":
        rows = [
            [KeyboardButton(text=BTN_NEW_GROUP), KeyboardButton(text=BTN_MY_GROUPS)],
            [KeyboardButton(text=BTN_NEW_ASSIGNMENT), KeyboardButton(text=BTN_TEACHER_ASSIGNMENTS)],
        ]
    else:
        rows = [
            [KeyboardButton(text=BTN_JOIN_GROUP), KeyboardButton(text=BTN_MY_GROUPS)],
            [KeyboardButton(text=BTN_STUDENT_ASSIGNMENTS), KeyboardButton(text=BTN_MY_GRADES)],
        ]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


# ---------- callback data ----------

class RoleCB(CallbackData, prefix="role"):
    role: str


class GroupCB(CallbackData, prefix="grp"):
    action: str  # pick
    group_id: int


class AsgCB(CallbackData, prefix="asg"):
    action: str  # view | subs | submit
    assignment_id: int


class SubCB(CallbackData, prefix="sub"):
    action: str  # view | grade
    submission_id: int


# ---------- inline klaviaturalar ----------

def role_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍🏫 O'qituvchi", callback_data=RoleCB(role="teacher").pack())],
            [InlineKeyboardButton(text="🎓 O'quvchi", callback_data=RoleCB(role="student").pack())],
        ]
    )


def groups_kb(groups: Sequence) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=shorten(g["name"], 40),
                    callback_data=GroupCB(action="pick", group_id=g["id"]).pack(),
                )
            ]
            for g in groups
        ]
    )


def assignments_kb(assignments: Sequence, *, marks: dict[int, str] | None = None) -> InlineKeyboardMarkup:
    marks = marks or {}
    rows = []
    for a in assignments:
        mark = marks.get(a["id"], "")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{shorten(a['title'], 35)}",
                    callback_data=AsgCB(action="view", assignment_id=a["id"]).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def assignment_actions_kb(assignment_id: int, role: str, *, submitted: bool = False) -> InlineKeyboardMarkup:
    if role == "teacher":
        button = InlineKeyboardButton(
            text="📥 Javoblar",
            callback_data=AsgCB(action="subs", assignment_id=assignment_id).pack(),
        )
    else:
        button = InlineKeyboardButton(
            text="♻️ Qayta topshirish" if submitted else "📤 Topshirish",
            callback_data=AsgCB(action="submit", assignment_id=assignment_id).pack(),
        )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def submissions_kb(submissions: Sequence) -> InlineKeyboardMarkup:
    rows = []
    for s in submissions:
        mark = f"[{s['grade']}] " if s["grade"] is not None else "🕒 "
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{mark}{shorten(s['student_name'], 35)}",
                    callback_data=SubCB(action="view", submission_id=s["id"]).pack(),
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def grade_kb(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✍️ Baho qo'yish",
                    callback_data=SubCB(action="grade", submission_id=submission_id).pack(),
                )
            ]
        ]
    )
