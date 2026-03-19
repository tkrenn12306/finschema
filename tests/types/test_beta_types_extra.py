from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import CurrencyMismatchError, InvalidFormatError, OutOfRangeError
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
