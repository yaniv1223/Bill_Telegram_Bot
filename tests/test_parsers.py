from decimal import Decimal

from expense_bot.parsers import parse_amount_text


def test_plain_number():
    assert parse_amount_text("15") == Decimal(15)


def test_comma_remove():
    assert parse_amount_text("80,000,000") == Decimal(80000000)


def test_invalid_returns_none():
    assert parse_amount_text("dmfoidmf") is None
