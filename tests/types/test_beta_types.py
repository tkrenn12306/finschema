from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import BaseModel, TypeAdapter

from finschema.errors import InvalidFormatError, OutOfRangeError
from finschema.types import (
    NAV,
    AssetClass,
    BasisPoints,
    CorporateActionType,
    MaturityDate,
    OrderType,
    Percentage,
    Price,
    Quantity,
    Rate,
    SettlementType,
    Side,
    Tenor,
    TimeInForce,
)


class EnumModel(BaseModel):
    side: Side
    asset_class: AssetClass
    order_type: OrderType
    tif: TimeInForce
    settlement_type: SettlementType
    ca_type: CorporateActionType


def test_price_valid() -> None:
    assert Price("10.25").as_decimal == Decimal("10.25")


def test_price_invalid_range() -> None:
    with pytest.raises(OutOfRangeError):
        Price(0)


def test_quantity_valid() -> None:
    assert Quantity("5").as_decimal == Decimal("5")


def test_quantity_invalid_zero() -> None:
    with pytest.raises(InvalidFormatError):
        Quantity(0)


def test_percentage_normalization() -> None:
    assert Percentage("45").as_decimal == Decimal("0.45")
    assert Percentage("0.45").as_decimal == Decimal("0.45")


def test_percentage_decimal_convention() -> None:
    assert Percentage("0.25", convention="decimal").as_decimal == Decimal("0.25")
    with pytest.raises(OutOfRangeError):
        Percentage("25", convention="decimal")


def test_rate_valid_and_invalid() -> None:
    assert Rate("0.05").as_decimal == Decimal("0.05")
    with pytest.raises(OutOfRangeError):
        Rate("1000")


def test_basis_points_conversion() -> None:
    bps = BasisPoints("100")
    assert bps.as_percent == Decimal("1")
    assert BasisPoints.from_percentage("1").as_decimal == Decimal("100")


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
    model = EnumModel(
        side="BUY",
        asset_class="CRYPTO",
        order_type="LIMIT",
        tif="DAY",
        settlement_type="DVP",
        ca_type="SPLIT",
    )
    assert model.side is Side.BUY
    assert model.asset_class is AssetClass.CRYPTO


def test_tenor_and_maturity_date() -> None:
    tenor = Tenor("3M")
    assert tenor.label == "3M"
    assert tenor.days == 90

    future = date.today() + timedelta(days=10)
    while future.weekday() >= 5:
        future += timedelta(days=1)
    maturity = MaturityDate(future.isoformat())
    assert maturity.isoformat() == future.isoformat()
