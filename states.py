"""FSM holatlari."""
from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    full_name = State()
    role = State()


class NewGroup(StatesGroup):
    name = State()


class JoinGroup(StatesGroup):
    code = State()


class NewAssignment(StatesGroup):
    group = State()
    title = State()
    description = State()
    deadline = State()


class Submit(StatesGroup):
    content = State()


class Grading(StatesGroup):
    grade = State()
