import asyncio

from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardRemove

from expense_bot.config import settings

dp = Dispatcher()


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "ברוך הבא לבוט של ניהול חשבונות",
        reply_markup=ReplyKeyboardRemove(),
    )


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
