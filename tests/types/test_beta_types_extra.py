from __future__ import annotations

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import CurrencyMismatchError, InvalidFormatError
from finschema.types import NAV, Money, Percentage, Price, Quantity


def test_money_subtract_currency_mismatch() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money("10", "EUR") - Money("1", "USD")


def test_repr_paths_for_beta_types() -> None:
    assert "Price(" in repr(Price("1"))
    assert "Quantity(" in repr(Quantity("1"))
    assert "Percentage(" in repr(Percentage("0.5"))
    assert "NAV(" in repr(NAV("100", "EUR", "2026-03-19"))


def test_type_adapter_instance_paths() -> None:
    assert TypeAdapter(Price).validate_python(Price("1")).as_decimal == 1
    assert TypeAdapter(Quantity).validate_python(Quantity("1")).as_decimal == 1
    assert TypeAdapter(Percentage).validate_python(Percentage("1")).as_decimal == 1


def test_percentage_negative_invalid() -> None:
    with pytest.raises(InvalidFormatError):
        Percentage("-0.1")


def test_nav_invalid_amount() -> None:
    with pytest.raises(InvalidFormatError):
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
