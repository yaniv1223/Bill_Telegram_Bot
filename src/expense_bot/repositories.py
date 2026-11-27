from decimal import Decimal

from sqlalchemy import select

from expense_bot.db import session_factory
from expense_bot.models import Account, CategoryRule, Transaction, User


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
        if remember:
            result = await session.scalars(
                select(CategoryRule).where(
                    CategoryRule.user_id == account.user_id,
                    CategoryRule.word == name,
                )
            )
            rule = result.first()
            if rule is None:
                session.add(
                    CategoryRule(user_id=account.user_id, word=name, category=category)
                )
            else:
                category = rule.category
        session.add(
            Transaction(
                account_id=account.id,
                amount=price,
                kind=kind,
                category=category,
                note=name,
            )
        )
        await session.commit()
