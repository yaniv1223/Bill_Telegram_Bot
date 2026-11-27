from decimal import Decimal

import pytest

from expense_bot.parsers import parse_amount_text, split_name_and_amount


def test_plain_number():
    assert parse_amount_text("15") == Decimal(15)


def test_comma_remove():
    assert parse_amount_text("80,000,000") == Decimal(80000000)


def test_invalid_returns_none():
    assert parse_amount_text("dmfoidmf") is None


@pytest.mark.parametrize(
    "text, expected",
    [
        ("קפה 15", ("קפה", Decimal(15))),
        ("15 קפה", ("קפה", Decimal(15))),
    ],
)
def test_split_name_and_amount(text, expected):
    assert split_name_and_amount(text) == expected
