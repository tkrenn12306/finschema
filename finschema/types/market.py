"""Market-level types."""

from __future__ import annotations

from finschema.reference import CURRENCY_DECIMALS

from ._pydantic import PydanticStrMixin


class CurrencyCode(PydanticStrMixin, str):
    def __new__(cls, value: str) -> CurrencyCode:
        normalized = value.upper().strip()
        if normalized not in CURRENCY_DECIMALS:
            from finschema.errors import InvalidCurrencyError

            raise InvalidCurrencyError(
                f"{normalized!r} is not a valid ISO 4217 currency code",
                details={"currency": normalized},
            )
        return str.__new__(cls, normalized)
