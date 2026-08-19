"""Har bir yangilanishda foydalanuvchini bazadan yuklaydigan middleware."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from db import queries


class UserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: User | None = data.get("event_from_user")
        data["user"] = await queries.get_user(tg_user.id) if tg_user else None
        return await handler(event, data)
