import asyncio
from decimal import Decimal, InvalidOperation

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)
from sqlalchemy import select

from expense_bot.config import settings
from expense_bot.db import session_factory
from expense_bot.models import Account, CategoryRule, Transaction, User

dp = Dispatcher()

pending: dict[tuple[int, int], tuple[str, Decimal, str]] = {}
awaiting_custom: dict[int, tuple[str, Decimal, str]] = {}

CATEGORIES = ["אוכל", "תחבורה", "קניות", "אחר"]


def category_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=c, callback_data=f"cat:{c}") for c in CATEGORIES
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def confirmation_text(kind: str, name: str, price: Decimal) -> str:
    label = "הוצאה" if kind == "expense" else "הכנסה"
    return f"נוספה {label}: {name}  בסכום של {price}"


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


async def find_category(session, user_id: int, word: str) -> str | None:
    result = await session.scalars(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id, CategoryRule.word == word
        )
    )
    rule = result.first()
    if rule is None:
        return None
    return rule.category


async def save_with_category(
    telegram_id: int,
    name: str,
    price: Decimal,
    kind: str,
    category: str,
    remember: bool = False,
) -> None:
    async with session_factory() as session:
        account = await get_or_create_account(session, telegram_id)
        session.add(
            Transaction(
                account_id=account.id,
                amount=price,
                kind=kind,
                category=category,
                note=name,
            )
        )
        if remember:
            existing = await find_category(session, account.user_id, name)
            if existing is None:
                session.add(
                    CategoryRule(user_id=account.user_id, word=name, category=category)
                )
        await session.commit()


async def save_transaction(message: Message, text: str, kind: str) -> None:
    awaiting_custom.pop(message.from_user.id, None)
    data = text.rsplit(maxsplit=1)
    if len(data) < 2:
        await message.answer("חסר שם או סכום, בדוק את ההודעה שוב\n")
        return
    try:
        price = Decimal(data[1])
    except InvalidOperation:
        await message.answer("לא הצלחתי לקרוא את הסכום\n")
        return
    if not price.is_finite() or price <= 0:
        await message.answer("הסכום חייב להיות מספר גדול מאפס\n")
        return
    name = data[0].strip()

    category = "הכנסה"
    if kind == "expense":
        async with session_factory() as session:
            account = await get_or_create_account(session, message.from_user.id)
            found = await find_category(session, account.user_id, name)
            await session.commit()
        if found is None:
            sent = await message.answer(
                f"איזו קטגוריה ל-{name}?", reply_markup=category_keyboard()
            )
            pending[(message.chat.id, sent.message_id)] = (name, price, kind)
            return
        category = found

    await save_with_category(message.from_user.id, name, price, kind, category)
    await message.answer(confirmation_text(kind, name, price))


@dp.callback_query(F.data.startswith("cat:"))
async def category_chosen(callback: CallbackQuery) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return
    category = callback.data.removeprefix("cat:")
    key = (callback.message.chat.id, callback.message.message_id)
    item = pending.pop(key, None)
    if item is None:
        await callback.answer("הבקשה פגה, שלח את ההוצאה שוב", show_alert=True)
        return
    name, price, kind = item
    if category == "אחר":
        awaiting_custom[callback.from_user.id] = item
        await callback.message.edit_text(f"כתוב את שם הקטגוריה ל-{name}:")
        await callback.answer()
        return
    await save_with_category(
        callback.from_user.id, name, price, kind, category, remember=True
    )
    await callback.message.edit_text(confirmation_text(kind, name, price))
    await callback.answer()


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


@dp.message(F.text)
async def custom_category_handler(message: Message) -> None:
    item = awaiting_custom.pop(message.from_user.id, None)
    if item is None:
        return
    name, price, kind = item
    category = message.text.strip()
    if not category:
        awaiting_custom[message.from_user.id] = item
        await message.answer("שם הקטגוריה ריק, כתוב אותו שוב")
        return
    await save_with_category(
        message.from_user.id, name, price, kind, category, remember=True
    )
    await message.answer(confirmation_text(kind, name, price))


async def main() -> None:
    bot = Bot(token=settings.bot_token)
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="התחלה"),
            BotCommand(command="add", description="הוספת הוצאה: /add קפה 15"),
            BotCommand(
                command="income", description="הוספת הכנסה: /income משכורת 8000"
            ),
        ]
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
