import asyncio
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove

from expense_bot.config import settings
from expense_bot.db import session_factory
from expense_bot.models import Transaction

dp = Dispatcher()


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "ברוך הבא לבוט של ניהול חשבונות",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Command("add"))
async def add_handler(message: Message, command: CommandObject) -> None:
    if command.args is None:
        await message.answer(
            "בבקשה תכניס את שם הפריט ואת העלות \n לדוגמא ./add קפה 15\n"
        )
        return
    data = command.args.rsplit(maxsplit=1)
    if len(data) < 2:
        await message.answer("חסר לך שם הפריט או המחיר תבדוק את הודעה שוב\n")
        return
    try:
        price = Decimal(data[1])
    except InvalidOperation:
        await message.answer("לא הצלחתי לקרוא את הסכום \n")
        return
    name = data[0]
    async with session_factory() as session:
        transaction = Transaction(
            account_id=1,
            amount=price,
            kind="expense",
            category=name,
            note=name,
        )
        session.add(transaction)
        await session.commit()
    await message.answer(f"הוסף בהצלחה {name} במחיר של {price}")


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
