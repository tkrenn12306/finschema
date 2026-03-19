"""Monetary types."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from finschema.errors import CurrencyMismatchError, InvalidFormatError, PrecisionError
from finschema.reference import get_currency_decimals

from .market import CurrencyCode


def _to_decimal(value: Decimal | int | float | str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise InvalidFormatError(
                f"{value!r} is not a valid decimal amount",
                details={"input": value},
            ) from exc
    raise InvalidFormatError(
        "Amount must be Decimal, int, float, or numeric string",
        details={"input_type": type(value).__name__},
    )


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: CurrencyCode

    def __init__(self, amount: Decimal | int | float | str, currency: str | CurrencyCode) -> None:
        object.__setattr__(self, "currency", CurrencyCode(str(currency)))
        decimal_amount = _to_decimal(amount)
        if not decimal_amount.is_finite():
            raise InvalidFormatError(
                "Amount must be finite",
                details={"amount": str(decimal_amount)},
            )
        decimals = get_currency_decimals(str(self.currency))
        raw_exponent = decimal_amount.as_tuple().exponent
        exponent = -raw_exponent if isinstance(raw_exponent, int) and raw_exponent < 0 else 0
        if exponent > decimals:
            suggestion = decimal_amount.quantize(Decimal(1).scaleb(-decimals))
            raise PrecisionError(
                f"{self.currency} does not allow {exponent} decimal places",
                details={
                    "amount": str(decimal_amount),
                    "max_decimals": decimals,
                    "suggestion": f"Money(amount={suggestion}, currency={self.currency!r})",
                },
            )
        object.__setattr__(self, "amount", decimal_amount)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot add {self.currency} and {other.currency}",
                details={"left": str(self.currency), "right": str(other.currency)},
            )
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot subtract {self.currency} and {other.currency}",
                details={"left": str(self.currency), "right": str(other.currency)},
            )
        return Money(self.amount - other.amount, self.currency)

    def __repr__(self) -> str:
        return f"Money({self.amount} {self.currency})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> Money:
            if isinstance(value, Money):
                return value
            if isinstance(value, dict):
                try:
                    return Money(amount=value["amount"], currency=value["currency"])
                except KeyError as exc:
                    raise InvalidFormatError(
                        "Money dict requires amount and currency",
                        details={"keys": sorted(value.keys())},
                    ) from exc
            raise InvalidFormatError(
                "Money requires a Money instance or {'amount', 'currency'} dict",
                details={"input_type": type(value).__name__},
            )

        return core_schema.no_info_plain_validator_function(_validate)
