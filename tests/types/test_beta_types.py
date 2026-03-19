from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import BaseModel, TypeAdapter

from finschema.errors import InvalidFormatError
from finschema.types import NAV, AssetClass, Percentage, Price, Quantity, Side


class EnumModel(BaseModel):
    side: Side
    asset_class: AssetClass


def test_price_valid() -> None:
    assert Price("10.25").as_decimal == Decimal("10.25")


def test_price_invalid() -> None:
    with pytest.raises(InvalidFormatError):
        Price(0)


def test_quantity_valid() -> None:
    assert Quantity("5").as_decimal == Decimal("5")


def test_quantity_invalid() -> None:
    with pytest.raises(InvalidFormatError):
        Quantity(-1)


def test_percentage_normalization() -> None:
    assert Percentage("45").as_decimal == Decimal("0.45")
    assert Percentage("0.45").as_decimal == Decimal("0.45")


def test_percentage_invalid_range() -> None:
    with pytest.raises(InvalidFormatError):
        Percentage("150")


def test_nav_valid() -> None:
    nav = NAV("198000.00", "EUR", "2026-03-19")
    assert nav.amount == Decimal("198000.00")
    assert str(nav.currency) == "EUR"
    assert nav.as_of_date.isoformat() == "2026-03-19"


def test_nav_type_adapter_from_dict() -> None:
    adapter = TypeAdapter(NAV)
    nav = adapter.validate_python(
        {"amount": "198000.00", "currency": "EUR", "as_of_date": "2026-03-19"}
    )
    assert nav.as_of_date == date(2026, 3, 19)


def test_enum_model_parsing() -> None:
    model = EnumModel(side="BUY", asset_class="EQUITY")
    assert model.side is Side.BUY
    assert model.asset_class is AssetClass.EQUITY
