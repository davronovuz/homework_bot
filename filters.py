"""Rol bo'yicha filtr."""
from typing import Any, Optional

from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject


class RoleFilter(BaseFilter):
    def __init__(self, role: str) -> None:
        self.role = role

    async def __call__(self, event: TelegramObject, user: Optional[Any] = None, **kwargs: Any) -> bool:
        return user is not None and user["role"] == self.role
