"""Baza bilan ishlovchi so'rovlar."""
import random
import string
from typing import Any, Optional, Sequence

import aiosqlite

from db.database import get_db

CODE_ALPHABET = string.ascii_uppercase + string.digits


# ---------- foydalanuvchilar ----------

async def get_user(tg_id: int) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute("SELECT * FROM users WHERE tg_id = ?", (tg_id,)) as cur:
        return await cur.fetchone()


async def get_user_by_id(user_id: int) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute("SELECT * FROM users WHERE id = ?", (user_id,)) as cur:
        return await cur.fetchone()


async def create_user(tg_id: int, full_name: str, username: Optional[str], role: str) -> aiosqlite.Row:
    db = get_db()
    await db.execute(
        "INSERT INTO users (tg_id, full_name, username, role) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (tg_id) DO UPDATE SET full_name = excluded.full_name, "
        "username = excluded.username, role = excluded.role",
        (tg_id, full_name, username, role),
    )
    await db.commit()
    user = await get_user(tg_id)
    assert user is not None
    return user


# ---------- guruhlar ----------

async def _generate_code() -> str:
    db = get_db()
    for _ in range(20):
        code = "".join(random.choices(CODE_ALPHABET, k=6))
        async with db.execute("SELECT 1 FROM groups WHERE code = ?", (code,)) as cur:
            if await cur.fetchone() is None:
                return code
    raise RuntimeError("Guruh kodini yaratib bo'lmadi, qayta urinib ko'ring.")


async def create_group(name: str, teacher_id: int) -> aiosqlite.Row:
    db = get_db()
    code = await _generate_code()
    cur = await db.execute(
        "INSERT INTO groups (name, code, teacher_id) VALUES (?, ?, ?)", (name, code, teacher_id)
    )
    await db.commit()
    group = await get_group(cur.lastrowid)
    assert group is not None
    return group


async def get_group(group_id: int) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute("SELECT * FROM groups WHERE id = ?", (group_id,)) as cur:
        return await cur.fetchone()


async def get_group_by_code(code: str) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute("SELECT * FROM groups WHERE code = ?", (code.upper().strip(),)) as cur:
        return await cur.fetchone()


async def teacher_groups(teacher_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT g.*, (SELECT COUNT(*) FROM memberships m WHERE m.group_id = g.id) AS students "
        "FROM groups g WHERE g.teacher_id = ? ORDER BY g.id DESC",
        (teacher_id,),
    ) as cur:
        return await cur.fetchall()


async def student_groups(student_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT g.*, u.full_name AS teacher_name FROM memberships m "
        "JOIN groups g ON g.id = m.group_id "
        "JOIN users u ON u.id = g.teacher_id "
        "WHERE m.student_id = ? ORDER BY g.id DESC",
        (student_id,),
    ) as cur:
        return await cur.fetchall()


async def join_group(group_id: int, student_id: int) -> bool:
    """Guruhga qo'shadi. Allaqachon a'zo bo'lsa False qaytaradi."""
    db = get_db()
    try:
        await db.execute(
            "INSERT INTO memberships (group_id, student_id) VALUES (?, ?)", (group_id, student_id)
        )
    except aiosqlite.IntegrityError:
        return False
    await db.commit()
    return True


async def group_students(group_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT u.* FROM memberships m JOIN users u ON u.id = m.student_id "
        "WHERE m.group_id = ? ORDER BY u.full_name",
        (group_id,),
    ) as cur:
        return await cur.fetchall()


# ---------- vazifalar ----------

async def create_assignment(
    group_id: int, title: str, description: Optional[str], deadline: Optional[str]
) -> int:
    db = get_db()
    cur = await db.execute(
        "INSERT INTO assignments (group_id, title, description, deadline) VALUES (?, ?, ?, ?)",
        (group_id, title, description, deadline),
    )
    await db.commit()
    return int(cur.lastrowid)


async def get_assignment(assignment_id: int) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT a.*, g.name AS group_name, g.teacher_id FROM assignments a "
        "JOIN groups g ON g.id = a.group_id WHERE a.id = ?",
        (assignment_id,),
    ) as cur:
        return await cur.fetchone()


async def teacher_assignments(teacher_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT a.*, g.name AS group_name, "
        "(SELECT COUNT(*) FROM submissions s WHERE s.assignment_id = a.id) AS submitted "
        "FROM assignments a JOIN groups g ON g.id = a.group_id "
        "WHERE g.teacher_id = ? ORDER BY a.id DESC",
        (teacher_id,),
    ) as cur:
        return await cur.fetchall()


async def student_assignments(student_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT a.*, g.name AS group_name, s.id AS submission_id, s.grade "
        "FROM assignments a "
        "JOIN memberships m ON m.group_id = a.group_id AND m.student_id = ? "
        "JOIN groups g ON g.id = a.group_id "
        "LEFT JOIN submissions s ON s.assignment_id = a.id AND s.student_id = ? "
        "ORDER BY a.id DESC",
        (student_id, student_id),
    ) as cur:
        return await cur.fetchall()


async def is_member(group_id: int, student_id: int) -> bool:
    db = get_db()
    async with db.execute(
        "SELECT 1 FROM memberships WHERE group_id = ? AND student_id = ?", (group_id, student_id)
    ) as cur:
        return await cur.fetchone() is not None


# ---------- javoblar ----------

async def upsert_submission(
    assignment_id: int,
    student_id: int,
    text: Optional[str],
    file_id: Optional[str],
    file_type: Optional[str],
) -> aiosqlite.Row:
    """Javobni saqlaydi; qayta topshirilsa eski javob yangilanadi va baho tozalanadi."""
    db = get_db()
    await db.execute(
        "INSERT INTO submissions (assignment_id, student_id, text, file_id, file_type) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT (assignment_id, student_id) DO UPDATE SET "
        "text = excluded.text, file_id = excluded.file_id, file_type = excluded.file_type, "
        "grade = NULL, comment = NULL, graded_at = NULL, submitted_at = datetime('now')",
        (assignment_id, student_id, text, file_id, file_type),
    )
    await db.commit()
    submission = await get_submission(assignment_id, student_id)
    assert submission is not None
    return submission


async def get_submission(assignment_id: int, student_id: int) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT * FROM submissions WHERE assignment_id = ? AND student_id = ?",
        (assignment_id, student_id),
    ) as cur:
        return await cur.fetchone()


async def get_submission_by_id(submission_id: int) -> Optional[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT s.*, u.full_name AS student_name, u.tg_id AS student_tg_id, "
        "a.title AS assignment_title, a.deadline AS deadline, g.teacher_id AS teacher_id "
        "FROM submissions s "
        "JOIN users u ON u.id = s.student_id "
        "JOIN assignments a ON a.id = s.assignment_id "
        "JOIN groups g ON g.id = a.group_id "
        "WHERE s.id = ?",
        (submission_id,),
    ) as cur:
        return await cur.fetchone()


async def assignment_submissions(assignment_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT s.*, u.full_name AS student_name FROM submissions s "
        "JOIN users u ON u.id = s.student_id "
        "WHERE s.assignment_id = ? ORDER BY s.submitted_at",
        (assignment_id,),
    ) as cur:
        return await cur.fetchall()


async def set_grade(submission_id: int, grade: int, comment: Optional[str] = None) -> None:
    db = get_db()
    await db.execute(
        "UPDATE submissions SET grade = ?, comment = ?, graded_at = datetime('now') WHERE id = ?",
        (grade, comment, submission_id),
    )
    await db.commit()


async def student_grades(student_id: int) -> Sequence[aiosqlite.Row]:
    db = get_db()
    async with db.execute(
        "SELECT s.grade, s.submitted_at, a.title, g.name AS group_name FROM submissions s "
        "JOIN assignments a ON a.id = s.assignment_id "
        "JOIN groups g ON g.id = a.group_id "
        "WHERE s.student_id = ? AND s.grade IS NOT NULL ORDER BY s.graded_at DESC",
        (student_id,),
    ) as cur:
        return await cur.fetchall()
