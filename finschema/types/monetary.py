"""Monetary types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from finschema.errors import (
    CurrencyMismatchError,
    InvalidFormatError,
    OutOfRangeError,
    PrecisionError,
)
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
                field="amount",
                expected="decimal-compatible numeric value",
                actual=value,
            ) from exc
    raise InvalidFormatError(
        "Amount must be Decimal, int, float, or numeric string",
        field="amount",
        expected="Decimal | int | float | str",
        actual=type(value).__name__,
    )


def _validate_finite(name: str, value: Decimal) -> None:
    if not value.is_finite():
        raise InvalidFormatError(
            f"{name} must be finite",
            field=name,
            expected="finite decimal",
            actual=str(value),
        )


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: CurrencyCode

    def __init__(self, amount: Decimal | int | float | str, currency: str | CurrencyCode) -> None:
        object.__setattr__(self, "currency", CurrencyCode(str(currency)))
        decimal_amount = _to_decimal(amount)
        _validate_finite("amount", decimal_amount)

        decimals = get_currency_decimals(str(self.currency), include_historical=True)
        raw_exponent = decimal_amount.as_tuple().exponent
        exponent = -raw_exponent if isinstance(raw_exponent, int) and raw_exponent < 0 else 0
        if exponent > decimals:
            suggestion = decimal_amount.quantize(Decimal(1).scaleb(-decimals))
            raise PrecisionError(
                f"{self.currency} does not allow {exponent} decimal places",
                field="amount",
                expected=f"<= {decimals} decimals",
                actual=str(decimal_amount),
                details={
                    "max_decimals": decimals,
                    "suggestion": f"Money(amount={suggestion}, currency={self.currency!r})",
                },
            )
        object.__setattr__(self, "amount", decimal_amount)

    def __add__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot add {self.currency} and {other.currency}",
                field="currency",
                expected=str(self.currency),
                actual=str(other.currency),
            )
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        if self.currency != other.currency:
            raise CurrencyMismatchError(
                f"Cannot subtract {self.currency} and {other.currency}",
                field="currency",
                expected=str(self.currency),
                actual=str(other.currency),
            )
        return Money(self.amount - other.amount, self.currency)

    def __str__(self) -> str:
        decimals = get_currency_decimals(str(self.currency), include_historical=True)
        quantized = self.amount.quantize(Decimal(1).scaleb(-decimals))
        return f"{quantized:,.{decimals}f} {self.currency}"

    def __repr__(self) -> str:
        return f"Money({self.amount} {self.currency})"

    def to_dict(self) -> dict[str, str]:
        return {"amount": str(self.amount), "currency": str(self.currency)}

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
                        field="money",
                        expected={"amount": "str|number", "currency": "str"},
                        actual=sorted(value.keys()),
                    ) from exc
            raise InvalidFormatError(
                "Money requires a Money instance or {'amount', 'currency'} dict",
                field="money",
                expected="Money | dict",
                actual=type(value).__name__,
            )

        return core_schema.no_info_plain_validator_function(
            _validate,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: value.to_dict()
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema: Any, _handler: Any) -> dict[str, Any]:
        return {
            "type": "object",
            "title": "Money",
            "description": "Amount and ISO 4217 currency.",
            "required": ["amount", "currency"],
            "properties": {
                "amount": {"type": "string", "examples": ["1000.50"]},
                "currency": {"type": "string", "pattern": r"^[A-Z]{3}$", "examples": ["EUR"]},
            },
            "examples": [{"amount": "1000.50", "currency": "EUR"}],
        }


@dataclass(frozen=True, slots=True)
class Price:
    value: Decimal

    DEFAULT_MIN = Decimal("0.0001")
    DEFAULT_MAX = Decimal("999999")

    def __init__(
        self,
        value: Decimal | int | float | str,
        *,
        min_value: Decimal | int | float | str = DEFAULT_MIN,
        max_value: Decimal | int | float | str = DEFAULT_MAX,
    ) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("price", decimal_value)
        min_decimal = _to_decimal(min_value)
        max_decimal = _to_decimal(max_value)
        if decimal_value < min_decimal or decimal_value > max_decimal:
            raise OutOfRangeError(
                "Price out of configured range",
                field="price",
                expected=f"{min_decimal} <= price <= {max_decimal}",
                actual=str(decimal_value),
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

    def __init__(
        self,
        value: Decimal | int | float | str,
        *,
        max_decimals: int | None = None,
    ) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("quantity", decimal_value)
        if decimal_value == 0:
            raise InvalidFormatError(
                "Quantity must be non-zero",
                field="quantity",
                expected="non-zero decimal",
                actual="0",
            )
        if max_decimals is not None:
            raw_exponent = decimal_value.as_tuple().exponent
            exponent = -raw_exponent if isinstance(raw_exponent, int) and raw_exponent < 0 else 0
            if exponent > max_decimals:
                raise PrecisionError(
                    "Quantity exceeds configured precision",
                    field="quantity",
                    expected=f"<= {max_decimals} decimals",
                    actual=str(decimal_value),
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

    def __init__(
        self,
        value: Decimal | int | float | str,
        *,
        convention: str = "auto",
    ) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("percentage", decimal_value)
        mode = convention.lower().strip()
        if mode not in {"auto", "decimal", "percent"}:
            raise InvalidFormatError(
                "Unsupported percentage convention",
                field="percentage",
                expected="auto | decimal | percent",
                actual=convention,
            )

        if mode == "decimal":
            if decimal_value < 0 or decimal_value > 1:
                raise OutOfRangeError(
                    "Decimal percentage must be in [0, 1]",
                    field="percentage",
                    expected="[0, 1]",
                    actual=str(decimal_value),
                )
            normalized = decimal_value
        elif mode == "percent":
            if decimal_value < 0 or decimal_value > 100:
                raise OutOfRangeError(
                    "Percent percentage must be in [0, 100]",
                    field="percentage",
                    expected="[0, 100]",
                    actual=str(decimal_value),
                )
            normalized = decimal_value / Decimal("100")
        else:
            if decimal_value < 0:
                raise OutOfRangeError(
                    "Percentage must be >= 0",
                    field="percentage",
                    expected=">= 0",
                    actual=str(decimal_value),
                )
            if decimal_value <= 1:
                normalized = decimal_value
            elif decimal_value <= 100:
                normalized = decimal_value / Decimal("100")
            else:
                raise OutOfRangeError(
                    "Percentage must be in [0, 1] or [0, 100]",
                    field="percentage",
                    expected="[0, 1] or [0, 100]",
                    actual=str(decimal_value),
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
class Rate:
    value: Decimal

    def __init__(
        self,
        value: Decimal | int | float | str,
        *,
        min_value: Decimal | int | float | str = Decimal("-1"),
        max_value: Decimal | int | float | str = Decimal("100"),
    ) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("rate", decimal_value)
        min_decimal = _to_decimal(min_value)
        max_decimal = _to_decimal(max_value)
        if decimal_value < min_decimal or decimal_value > max_decimal:
            raise OutOfRangeError(
                "Rate out of configured range",
                field="rate",
                expected=f"{min_decimal} <= rate <= {max_decimal}",
                actual=str(decimal_value),
            )
        object.__setattr__(self, "value", decimal_value)

    @property
    def as_decimal(self) -> Decimal:
        return self.value


@dataclass(frozen=True, slots=True)
class BasisPoints:
    value: Decimal

    def __init__(self, value: Decimal | int | float | str) -> None:
        decimal_value = _to_decimal(value)
        _validate_finite("basis_points", decimal_value)
        object.__setattr__(self, "value", decimal_value)

    @property
    def as_decimal(self) -> Decimal:
        return self.value

    @property
    def as_percent(self) -> Decimal:
        return self.value / Decimal("100")

    def to_percentage(self) -> Percentage:
        return Percentage(self.as_percent, convention="percent")

    @classmethod
    def from_percentage(cls, percentage: Percentage | Decimal | int | float | str) -> BasisPoints:
        if isinstance(percentage, Percentage):
            percent_value = percentage.as_percent
        else:
            # from_percentage expects percent units, e.g. 1 => 1%.
            percent_value = Percentage(percentage, convention="percent").as_percent
        return cls(percent_value * Decimal("100"))

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> BasisPoints:
            if isinstance(value, BasisPoints):
                return value
            return BasisPoints(value)

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
            raise OutOfRangeError(
                "NAV amount must be > 0",
                field="amount",
                expected="> 0",
                actual=str(decimal_amount),
            )
        object.__setattr__(self, "amount", decimal_amount)
        object.__setattr__(self, "currency", CurrencyCode(str(currency), include_historical=True))
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
                            field="nav",
                            expected={
                                "amount": "str|number",
                                "currency": "str",
                                "as_of_date": "date",
                            },
                            actual=sorted(value.keys()),
                        )
                    return NAV(
                        amount=value["amount"],
                        currency=value["currency"],
                        as_of_date=as_of_date,
                    )
                except KeyError as exc:
                    raise InvalidFormatError(
                        "NAV dict requires amount, currency, and as_of_date",
                        field="nav",
                        expected={"amount": "str|number", "currency": "str", "as_of_date": "date"},
                        actual=sorted(value.keys()),
                    ) from exc
            raise InvalidFormatError(
                "NAV requires NAV instance or {'amount', 'currency', 'as_of_date'} dict",
                field="nav",
                expected="NAV | dict",
                actual=type(value).__name__,
            )

        return core_schema.no_info_plain_validator_function(_validate)
