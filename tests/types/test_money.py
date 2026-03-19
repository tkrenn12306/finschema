from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import (
    CurrencyMismatchError,
    InvalidCurrencyError,
    InvalidFormatError,
    PrecisionError,
)
from finschema.types import Money


class _MoneyModel(BaseModel):
    notional: Money


def test_money_valid() -> None:
    money = Money(amount=1000.50, currency="EUR")
    assert money.amount == Decimal("1000.50")
    assert str(money.currency) == "EUR"


def test_money_precision_for_jpy() -> None:
    with pytest.raises(PrecisionError) as exc:
        Money(amount=1000.55, currency="JPY")
    assert exc.value.details["expected"] == "<= 0 decimals"


def test_money_currency_mismatch() -> None:
    eur = Money(100, "EUR")
    usd = Money(200, "USD")
    with pytest.raises(CurrencyMismatchError):
        _ = eur + usd


def test_money_addition_same_currency() -> None:
    left = Money(100, "EUR")
    right = Money(20.25, "EUR")
    total = left + right
    assert total.amount == Decimal("120.25")
    assert str(total.currency) == "EUR"


def test_money_subtraction_same_currency() -> None:
    left = Money(100, "EUR")
    right = Money(20.25, "EUR")
    total = left - right
    assert total.amount == Decimal("79.75")


def test_money_invalid_currency() -> None:
    with pytest.raises(InvalidCurrencyError):
        Money(10, "XXX")


def test_money_invalid_decimal_string() -> None:
    with pytest.raises(InvalidFormatError):
        Money("abc", "EUR")


def test_money_invalid_amount_type() -> None:
    with pytest.raises(InvalidFormatError):
        Money(object(), "EUR")  # type: ignore[arg-type]


def test_money_non_finite_amount() -> None:
    with pytest.raises(InvalidFormatError):
        Money("NaN", "EUR")


def test_money_repr() -> None:
    assert repr(Money("10.00", "EUR")) == "Money(10.00 EUR)"


def test_money_str_format() -> None:
    assert str(Money("1000.5", "EUR")) == "1,000.50 EUR"


def test_money_to_dict_serialization() -> None:
    model = _MoneyModel(notional={"amount": "1000.50", "currency": "EUR"})
    assert model.model_dump() == {"notional": {"amount": "1000.50", "currency": "EUR"}}


def test_money_type_adapter_accepts_money_instance() -> None:
    adapter = TypeAdapter(Money)
    money = Money("10.00", "EUR")
    assert adapter.validate_python(money) is money


def test_money_type_adapter_rejects_missing_currency_key() -> None:
    adapter = TypeAdapter(Money)
    with pytest.raises(PydanticValidationError):
        adapter.validate_python({"amount": "10.00"})


def test_money_type_adapter_rejects_wrong_input_type() -> None:
    adapter = TypeAdapter(Money)
    with pytest.raises(PydanticValidationError):
        adapter.validate_python("10.00")
