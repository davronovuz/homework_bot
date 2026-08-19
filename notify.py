"""Xabarnomalarni xavfsiz yuborish (bloklangan foydalanuvchi botni yiqitmasin)."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

logger = logging.getLogger(__name__)


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id, text, **kwargs)
        return True
    except TelegramAPIError as error:
        logger.warning("Xabar yuborilmadi (chat_id=%s): %s", chat_id, error)
        return False
