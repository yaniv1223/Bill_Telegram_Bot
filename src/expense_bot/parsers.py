from decimal import Decimal, InvalidOperation


def parse_amount_text(amount: str) -> Decimal | None:
    try:
        clean_amount = Decimal(amount.replace(",", ""))
    except InvalidOperation:
        return None
    return clean_amount
