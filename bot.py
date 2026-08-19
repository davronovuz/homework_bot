"""Uy vazifalari boti — ishga tushirish nuqtasi."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN, check_config
from db import close_db, init_db
from handlers import setup_routers
from middlewares import UserMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

COMMANDS = [
    BotCommand(command="start", description="Boshlash / menyu"),
    BotCommand(command="yordam", description="Yordam"),
    BotCommand(command="bekor", description="Amalni bekor qilish"),
]


async def main() -> None:
    check_config()
    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(UserMiddleware())
    dp.include_router(setup_routers())

    await bot.set_my_commands(COMMANDS)
    await bot.delete_webhook(drop_pending_updates=True)
    me = await bot.get_me()
    logger.info("Bot ishga tushdi: @%s", me.username)
    try:
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Chiqildi.")
