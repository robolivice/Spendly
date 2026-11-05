from __future__ import annotations

DEFAULT_CURRENCY = "INR"

CURRENCIES = {
    "INR": {
        "code": "INR",
        "symbol": "₹",
        "label": "INR (₹)",
        "locale": "en-IN",
    },
    "USD": {
        "code": "USD",
        "symbol": "$",
        "label": "USD ($)",
        "locale": "en-US",
    },
    "EUR": {
        "code": "EUR",
        "symbol": "€",
        "label": "EUR (€)",
        "locale": "de-DE",
    },
    "GBP": {
        "code": "GBP",
        "symbol": "£",
        "label": "GBP (£)",
        "locale": "en-GB",
    },
}

CURRENCY_CODES = tuple(CURRENCIES)


def normalize(code: str | None) -> str:
    if isinstance(code, str):
        value = code.strip().upper()
        if value in CURRENCIES:
            return value
    return DEFAULT_CURRENCY


def _group_western(whole: str) -> str:
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    return ",".join(groups)


def _group_indian(whole: str) -> str:
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return ",".join(groups + [tail])


def _decimal(value: float) -> tuple[str, str]:
    fixed = f"{abs(value):.2f}"
    whole, fraction = fixed.split(".")
    return whole, fraction


def format_amount(value, code: str | None = None) -> str:
    selected = normalize(code)
    try:
        amount = float(value)
    except (TypeError, ValueError):
        amount = 0.0
    if amount != amount or amount in (float("inf"), float("-inf")):
        amount = 0.0
    whole, fraction = _decimal(amount)
    if selected == "INR":
        grouped = _group_indian(whole)
        text = f"{CURRENCIES[selected]['symbol']}{grouped}.{fraction}"
    elif selected == "EUR":
        grouped = _group_western(whole).replace(",", ".")
        text = f"{grouped},{fraction} {CURRENCIES[selected]['symbol']}"
    else:
        grouped = _group_western(whole)
        text = f"{CURRENCIES[selected]['symbol']}{grouped}.{fraction}"
    return f"-{text}" if amount < 0 else text
