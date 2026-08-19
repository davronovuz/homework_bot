"""SQLite ulanishi va jadvallar sxemasi."""
import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id      INTEGER NOT NULL UNIQUE,
    full_name  TEXT    NOT NULL,
    username   TEXT,
    role       TEXT    NOT NULL CHECK (role IN ('teacher', 'student')),
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS groups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT    NOT NULL,
    code       TEXT    NOT NULL UNIQUE,
    teacher_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS memberships (
    group_id   INTEGER NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    joined_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, student_id)
);

CREATE TABLE IF NOT EXISTS assignments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id    INTEGER NOT NULL REFERENCES groups (id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    description TEXT,
    deadline    TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS submissions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    assignment_id INTEGER NOT NULL REFERENCES assignments (id) ON DELETE CASCADE,
    student_id    INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    text          TEXT,
    file_id       TEXT,
    file_type     TEXT,
    grade         INTEGER,
    comment       TEXT,
    submitted_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    graded_at     TEXT,
    UNIQUE (assignment_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_assignments_group ON assignments (group_id);
CREATE INDEX IF NOT EXISTS idx_memberships_student ON memberships (student_id);
CREATE INDEX IF NOT EXISTS idx_submissions_assignment ON submissions (assignment_id);
"""

_conn: aiosqlite.Connection | None = None


async def init_db() -> aiosqlite.Connection:
    """Bazaga ulanadi va jadvallarni yaratadi."""
    global _conn
    if _conn is None:
        _conn = await aiosqlite.connect(DB_PATH)
        _conn.row_factory = aiosqlite.Row
        await _conn.execute("PRAGMA foreign_keys = ON")
        await _conn.execute("PRAGMA journal_mode = WAL")
        await _conn.executescript(SCHEMA)
        await _conn.commit()
    return _conn


def get_db() -> aiosqlite.Connection:
    """Ochiq ulanishni qaytaradi (init_db dan keyin chaqiriladi)."""
    if _conn is None:
        raise RuntimeError("Baza ulanmagan: avval init_db() ni chaqiring.")
    return _conn


async def close_db() -> None:
    global _conn
    if _conn is not None:
        await _conn.close()
        _conn = None
