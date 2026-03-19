"""Monetary types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from finschema.errors import CurrencyMismatchError, InvalidFormatError, PrecisionError
from finschema.reference import get_currency_decimals

from .market import CurrencyCode
from .temporal import BusinessDate


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


def _validate_finite(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise InvalidFormatError(
            f"{name} must be finite",
            details={name: str(value)},
        )


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: CurrencyCode

    def __init__(self, amount: Decimal | int | float | str, currency: str | CurrencyCode) -> None:
        object.__setattr__(self, "currency", CurrencyCode(str(currency)))
        decimal_amount = _to_decimal(amount)
        _validate_finite("amount", decimal_amount)

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


@dataclass(frozen=True, slots=True)
class Price:
    value: Decimal

    def __init__(self, value: Decimal | int | float | str) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("price", decimal_value)
        if decimal_value <= 0:
            raise InvalidFormatError(
                "Price must be > 0",
                details={"price": str(decimal_value)},
            )
        object.__setattr__(self, "value", decimal_value)

    @property
    def as_decimal(self) -> Decimal:
        return self.value

    def __repr__(self) -> str:
        return f"Price({self.value})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> Price:
            if isinstance(value, Price):
                return value
            return Price(value)

        return core_schema.no_info_plain_validator_function(_validate)


@dataclass(frozen=True, slots=True)
class Quantity:
    value: Decimal

    def __init__(self, value: Decimal | int | float | str) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("quantity", decimal_value)
        if decimal_value <= 0:
            raise InvalidFormatError(
                "Quantity must be > 0",
                details={"quantity": str(decimal_value)},
            )
        object.__setattr__(self, "value", decimal_value)

    @property
    def as_decimal(self) -> Decimal:
        return self.value

    def __repr__(self) -> str:
        return f"Quantity({self.value})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> Quantity:
            if isinstance(value, Quantity):
                return value
            return Quantity(value)

        return core_schema.no_info_plain_validator_function(_validate)


@dataclass(frozen=True, slots=True)
class Percentage:
    value: Decimal

    def __init__(self, value: Decimal | int | float | str) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("percentage", decimal_value)
        if decimal_value < 0:
            raise InvalidFormatError(
                "Percentage must be >= 0",
                details={"percentage": str(decimal_value)},
            )
        normalized = decimal_value
        if decimal_value > 1:
            if decimal_value <= 100:
                normalized = decimal_value / Decimal("100")
            else:
                raise InvalidFormatError(
                    "Percentage must be in [0, 1] or [0, 100]",
                    details={"percentage": str(decimal_value)},
                )
        object.__setattr__(self, "value", normalized)

    @property
    def as_decimal(self) -> Decimal:
        return self.value

    @property
    def as_percent(self) -> Decimal:
        return self.value * Decimal("100")

    def __repr__(self) -> str:
        return f"Percentage({self.as_percent}%)"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> Percentage:
            if isinstance(value, Percentage):
                return value
            return Percentage(value)

        return core_schema.no_info_plain_validator_function(_validate)


@dataclass(frozen=True, slots=True)
class NAV:
    amount: Decimal
    currency: CurrencyCode
    as_of_date: BusinessDate

    def __init__(
        self,
        amount: Decimal | int | float | str,
        currency: str | CurrencyCode,
        as_of_date: str | date | BusinessDate,
    ) -> None:
        decimal_amount = _to_decimal(amount)
        _validate_finite("amount", decimal_amount)
        if decimal_amount <= 0:
            raise InvalidFormatError(
                "NAV amount must be > 0",
                details={"amount": str(decimal_amount)},
            )
        object.__setattr__(self, "amount", decimal_amount)
        object.__setattr__(self, "currency", CurrencyCode(str(currency)))
        object.__setattr__(self, "as_of_date", BusinessDate(as_of_date))

    def __repr__(self) -> str:
        return f"NAV({self.amount} {self.currency} @ {self.as_of_date.isoformat()})"

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> NAV:
            if isinstance(value, NAV):
                return value
            if isinstance(value, dict):
                try:
                    as_of_date = value.get("as_of_date", value.get("date", value.get("nav_date")))
                    if as_of_date is None:
                        raise InvalidFormatError(
                            "NAV dict requires amount, currency, and as_of_date",
                            details={"keys": sorted(value.keys())},
                        )
                    return NAV(
                        amount=value["amount"],
                        currency=value["currency"],
                        as_of_date=as_of_date,
                    )
                except KeyError as exc:
                    raise InvalidFormatError(
                        "NAV dict requires amount, currency, and as_of_date",
                        details={"keys": sorted(value.keys())},
                    ) from exc
            raise InvalidFormatError(
                "NAV requires NAV instance or {'amount', 'currency', 'as_of_date'} dict",
                details={"input_type": type(value).__name__},
            )

        return core_schema.no_info_plain_validator_function(_validate)
