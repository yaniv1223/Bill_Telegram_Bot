from decimal import Decimal, InvalidOperation


def parse_amount_text(amount: str) -> Decimal | None:
    try:
        clean_amount = Decimal(amount.replace(",", ""))
    except InvalidOperation:
        return None
    return clean_amount


def split_name_and_amount(text: str) -> tuple[str, Decimal] | None:
    parts = text.split()
    if len(parts) < 2:
        return None
    price = parse_amount_text(parts[-1])
    if price is not None:
        return " ".join(parts[:-1]), price
    price = parse_amount_text(parts[0])
    if price is not None:
        return " ".join(parts[1:]), price
    return None
