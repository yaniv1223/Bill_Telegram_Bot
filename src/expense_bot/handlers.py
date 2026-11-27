from decimal import Decimal

from aiogram import Dispatcher, F
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardRemove,
)

from expense_bot.db import session_factory
from expense_bot.parsers import parse_amount_text
from expense_bot.repositories import (
    find_category,
    get_or_create_account,
    save_with_category,
)

dp = Dispatcher()

pending: dict[tuple[int, int], tuple[str, Decimal, str]] = {}
awaiting_custom: dict[int, tuple[str, Decimal, str]] = {}

CATEGORIES = ["אוכל", "תחבורה", "קניות", "אחר"]

WELCOME_TEXT = (
    "היי! 👋 אני כאן כדי לעזור לך לדעת לאן הכסף הולך.\n"
    "\n"
    "אז איך זה עובד?\n"
    "כשרוצים להוסיף מידע למערכת:\n"
    "1) מתחילים במילה שמורה: הוצאה או הכנסה\n"
    "2) כותבים את השם\n"
    "3) כותבים את הסכום\n"
    "\n"
    "לדוגמה:\n"
    "💸 הוצאה קפה 15\n"
    "💰 הכנסה משכורת 8000\n"
    "\n"
    "אם מדובר בהוצאה, צריך גם לבחור קטגוריה.\n"
    "שימו לב: בלחיצה על האפשרות אחר, תוכלו להכניס קטגוריה באופן ידני."
)


def category_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=c, callback_data=f"cat:{c}") for c in CATEGORIES
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def confirmation_text(kind: str, name: str, price: Decimal) -> str:
    label = "הוצאה" if kind == "expense" else "הכנסה"
    return f"נוספה {label}: {name} בסכום של {price}"


async def save_transaction(message: Message, text: str, kind: str) -> None:
    awaiting_custom.pop(message.from_user.id, None)
    data = text.rsplit(maxsplit=1)
    if len(data) < 2:
        await message.answer("חסר שם או סכום, בדוק את ההודעה שוב\n")
        return
    price = parse_amount_text(data[1])
    if price is None:
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
@dp.message(Command("help"))
async def handle_start(message: Message) -> None:
    await message.answer(WELCOME_TEXT, reply_markup=ReplyKeyboardRemove())


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
