from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import (
    CurrencyMismatchError,
    InvalidFormatError,
    OutOfRangeError,
    PrecisionError,
)
from finschema.types import NAV, BasisPoints, MaturityDate, Money, Percentage, Price, Quantity, Rate


def test_money_subtract_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money("10", "EUR") - Money("1", "USD")


def test_repr_paths_for_types() -> None:
    assert "Price(" in repr(Price("1"))
    assert "Quantity(" in repr(Quantity("1"))
    assert "Percentage(" in repr(Percentage("0.5"))
    assert "NAV(" in repr(NAV("100", "EUR", "2026-03-19"))


def test_type_adapter_instance_paths() -> None:
    assert TypeAdapter(Price).validate_python(Price("1")).as_decimal == 1
    assert TypeAdapter(Quantity).validate_python(Quantity("1")).as_decimal == 1
    assert TypeAdapter(Percentage).validate_python(Percentage("1")).as_decimal == 1
    assert TypeAdapter(BasisPoints).validate_python(BasisPoints("1")).as_decimal == 1


def test_percentage_negative_invalid() -> None:
    with pytest.raises(OutOfRangeError):
        Percentage("-0.1")


def test_nav_invalid_amount() -> None:
    with pytest.raises(OutOfRangeError):
        NAV("0", "EUR", "2026-03-19")


def test_nav_type_adapter_missing_date() -> None:
    with pytest.raises(PydanticValidationError):
        TypeAdapter(NAV).validate_python({"amount": "1", "currency": "EUR"})


def test_nav_type_adapter_missing_amount() -> None:
    with pytest.raises(PydanticValidationError):
        TypeAdapter(NAV).validate_python({"currency": "EUR", "as_of_date": "2026-03-19"})


def test_nav_type_adapter_wrong_input_type() -> None:
    with pytest.raises(PydanticValidationError):
        TypeAdapter(NAV).validate_python(["bad"])  # type: ignore[list-item]


def test_rate_custom_range() -> None:
    assert Rate("1", min_value="0", max_value="10").as_decimal == 1
    with pytest.raises(OutOfRangeError):
        Rate("11", min_value="0", max_value="10")


def test_maturity_date_must_be_future() -> None:
    with pytest.raises(OutOfRangeError):
        MaturityDate(date.today().isoformat())
    assert MaturityDate((date.today() + timedelta(days=1)).isoformat())


def test_basis_points_from_percentage_invalid() -> None:
    with pytest.raises(InvalidFormatError):
        BasisPoints.from_percentage("bad")


def test_quantity_precision_error() -> None:
    with pytest.raises(PrecisionError):
        Quantity("1.234", max_decimals=2)


def test_percentage_additional_error_branches() -> None:
    with pytest.raises(InvalidFormatError):
        Percentage("1", convention="unknown")
    with pytest.raises(OutOfRangeError):
        Percentage("101", convention="percent")
    with pytest.raises(OutOfRangeError):
        Percentage("101", convention="auto")


def test_basis_points_conversion_paths() -> None:
    bps = BasisPoints("100")
    as_percentage = bps.to_percentage()
    assert as_percentage.as_decimal == Decimal("0.01")
    assert as_percentage.as_percent == Decimal("1")
    assert BasisPoints.from_percentage(Percentage("1", convention="percent")).as_decimal == 100
    assert TypeAdapter(BasisPoints).validate_python("25").as_decimal == 25
