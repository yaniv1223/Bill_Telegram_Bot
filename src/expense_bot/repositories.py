import secrets
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import func, select

from expense_bot.db import session_factory
from expense_bot.models import Account, AccountMember, CategoryRule, Transaction, User


async def get_or_create_user(session, telegram_id: int) -> User:
    result = await session.scalars(select(User).where(User.telegram_id == telegram_id))
    user = result.first()
    if user is None:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.flush()
    return user


async def get_or_create_account(session, telegram_id: int) -> Account:
    user = await get_or_create_user(session, telegram_id)

    result = await session.scalars(
        select(Account)
        .join(AccountMember, AccountMember.account_id == Account.id)
        .where(AccountMember.user_id == user.id)
        .order_by(AccountMember.id)
    )
    account = result.first()
    if account is not None:
        return account

    result = await session.scalars(select(Account).where(Account.user_id == user.id))
    account = result.first()
    if account is None:
        account = Account(user_id=user.id, name="Main", currency="ILS")
        session.add(account)
        await session.flush()

    session.add(AccountMember(account_id=account.id, user_id=user.id))
    await session.flush()
    return account


async def create_invite_code(telegram_id: int) -> str:
    async with session_factory() as session:
        account = await get_or_create_account(session, telegram_id)
        if account.invite_code is None:
            account.invite_code = secrets.token_hex(4)
        code = account.invite_code
        await session.commit()
        return code


async def join_account(telegram_id: int, code: str) -> bool:
    async with session_factory() as session:
        result = await session.scalars(
            select(Account).where(Account.invite_code == code)
        )
        account = result.first()
        if account is None:
            return False
        user = await get_or_create_user(session, telegram_id)
        result = await session.scalars(
            select(AccountMember).where(
                AccountMember.account_id == account.id,
                AccountMember.user_id == user.id,
            )
        )
        if result.first() is None:
            session.add(AccountMember(account_id=account.id, user_id=user.id))
        await session.commit()
        return True


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


async def month_summary(
    telegram_id: int,
) -> tuple[Decimal, Decimal, list[tuple[str, Decimal]]]:
    start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    async with session_factory() as session:
        account = await get_or_create_account(session, telegram_id)
        account_id = account.id
        await session.commit()
        result = await session.execute(
            select(
                Transaction.kind,
                Transaction.category,
                func.sum(Transaction.amount),
            )
            .where(
                Transaction.account_id == account_id,
                Transaction.created_at >= start,
            )
            .group_by(Transaction.kind, Transaction.category)
        )
        rows = result.all()

    expense_total = Decimal(0)
    income_total = Decimal(0)
    by_category = []
    for kind, category, total in rows:
        if kind == "expense":
            expense_total += total
            by_category.append((category, total))
        else:
            income_total += total
    by_category.sort(key=lambda row: row[1], reverse=True)
    return expense_total, income_total, by_category
