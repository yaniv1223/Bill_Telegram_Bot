import asyncio

from aiogram import Bot

from expense_bot.config import settings
from expense_bot.handlers import dp


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    await bot.delete_my_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
