"""ISO 4217 active currency codes and minor units for alpha checks."""

from __future__ import annotations

from finschema.errors import InvalidCurrencyError

CURRENCY_DECIMALS: dict[str, int] = {
    "AED": 2,
    "ARS": 2,
    "AUD": 2,
    "BGN": 2,
    "BHD": 3,
    "BRL": 2,
    "CAD": 2,
    "CHF": 2,
    "CLP": 0,
    "CNY": 2,
    "CZK": 2,
    "DKK": 2,
    "EGP": 2,
    "EUR": 2,
    "GBP": 2,
    "HKD": 2,
    "HUF": 2,
    "IDR": 2,
    "ILS": 2,
    "INR": 2,
    "ISK": 0,
    "JPY": 0,
    "KRW": 0,
    "KWD": 3,
    "MAD": 2,
    "MXN": 2,
    "MYR": 2,
    "NOK": 2,
    "NZD": 2,
    "PHP": 2,
    "PLN": 2,
    "QAR": 2,
    "RON": 2,
    "SAR": 2,
    "SEK": 2,
    "SGD": 2,
    "THB": 2,
    "TRY": 2,
    "TWD": 2,
    "UAH": 2,
    "USD": 2,
    "UYU": 2,
    "ZAR": 2,
}


def get_currency_decimals(code: str) -> int:
    normalized = code.upper()
    decimals = CURRENCY_DECIMALS.get(normalized)
    if decimals is None:
        raise InvalidCurrencyError(
            f"{normalized!r} is not a valid ISO 4217 currency code",
            details={"currency": normalized},
        )
    return decimals
