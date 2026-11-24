import asyncio
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy import select

from expense_bot.config import settings
from expense_bot.db import session_factory
from expense_bot.models import Account, Transaction, User

dp = Dispatcher()


async def get_or_create_account(session, telegram_id: int) -> Account:
    result = await session.scalars(select(User).where(User.telegram_id == telegram_id))
    user = result.first()
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.flush()

    result = await session.scalars(select(Account).where(Account.user_id == user.id))
    account = result.first()
    if account is None:
        account = Account(user_id=user.id, name="Main", currency="ILS")
        session.add(account)
        await session.flush()
    return account


async def save_transaction(message: Message, text: str, kind: str) -> None:
    data = text.rsplit(maxsplit=1)
    if len(data) < 2:
        await message.answer("חסר שם או סכום, בדוק את ההודעה שוב\n")
        return
    try:
        price = Decimal(data[1])
    except InvalidOperation:
        await message.answer("לא הצלחתי לקרוא את הסכום\n")
        return
    name = data[0]
    async with session_factory() as session:
        account = await get_or_create_account(session, message.from_user.id)
        session.add(
            Transaction(
                account_id=account.id,
                amount=price,
                kind=kind,
                category=name,
                note=name,
            )
        )
        await session.commit()
    label = "הוצאה" if kind == "expense" else "הכנסה"
    await message.answer(f"נוספה {label}: {name} בסכום של {price}")


@dp.message(CommandStart())
async def handle_start(message: Message) -> None:
    await message.answer(
        "ברוך הבא לבוט של ניהול חשבונות",
        reply_markup=ReplyKeyboardRemove(),
    )


@dp.message(Command("add"))
async def add_handler(message: Message, command: CommandObject) -> None:
    if command.args is None:
        await message.answer("לדוגמה: /add קפה 15\n")
        return
    await save_transaction(message, command.args, "expense")


@dp.message(Command("income"))
async def income_handler(message: Message, command: CommandObject) -> None:
    if command.args is None:
        await message.answer("לדוגמה: /income משכורת 8000\n")
        return
    await save_transaction(message, command.args, "income")


@dp.message(F.text.startswith("הוצאה "))
async def expense_text_handler(message: Message) -> None:
    await save_transaction(message, message.text.removeprefix("הוצאה "), "expense")


@dp.message(F.text.startswith("הכנסה "))
async def income_text_handler(message: Message) -> None:
    await save_transaction(message, message.text.removeprefix("הכנסה "), "income")


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
