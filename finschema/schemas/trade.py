"""Trade and order schemas."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import (
    ISIN,
    LEI,
    MIC,
    AssetClass,
    BusinessDate,
    CurrencyCode,
    Money,
    OrderType,
    Percentage,
    Price,
    Quantity,
    Side,
    TimeInForce,
)

_SETTLEMENT_CYCLES: dict[tuple[str, str], int] = {
    ("US", "EQUITY"): 1,
    ("EU", "EQUITY"): 2,
    ("US", "TREASURY"): 1,
}
_DEFAULT_SETTLEMENT_DAYS = 1
_PERCENTAGE_TOLERANCE = Decimal("0.001")


def _add_business_days(value: date, days: int) -> BusinessDate:
    current = date(value.year, value.month, value.day)
    remaining = max(days, 0)
    while remaining > 0:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return BusinessDate(current)


def _quantity_decimal(value: Quantity) -> Decimal:
    return Decimal(str(value.as_decimal))


class Execution(BaseModel):
    trade_id: str
    fill_price: Price
    fill_quantity: Quantity
    fill_time: datetime
    execution_venue: MIC | None = None

    model_config = ConfigDict(validate_assignment=True)


class Allocation(BaseModel):
    trade_id: str
    portfolio_id: str
    quantity: Quantity
    allocation_pct: Percentage | None = None

    model_config = ConfigDict(validate_assignment=True)


class Order(BaseModel):
    order_id: str
    isin: ISIN
    side: Side
    quantity: Quantity
    order_type: OrderType
    time_in_force: TimeInForce
    limit_price: Price | None = None
    stop_price: Price | None = None

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_order_logic(self) -> Order:
        if self.order_type == OrderType.LIMIT and self.limit_price is None:
            raise ValueError(
                "limit_price is required for LIMIT orders [rule: order_limit_requires_price]"
            )
        return self


class Trade(BaseModel):
    trade_id: str
    isin: ISIN
    side: Side
    quantity: Quantity
    price: Price
    currency: CurrencyCode
    trade_date: BusinessDate
    settlement_date: BusinessDate
    counterparty_lei: LEI | None = None
    venue: MIC | None = None
    commission: Money | None = None
    market: str | None = None
    asset_class: AssetClass | None = None
    instrument_type: str | None = None
    executions: list[Execution] | None = None
    allocations: list[Allocation] | None = None

    model_config = ConfigDict(validate_assignment=True)

    def _expected_settlement_days(self) -> int:
        market = (self.market or "").upper().strip()
        instrument_type = (self.instrument_type or "").upper().strip()
        if market and instrument_type:
            by_instrument = _SETTLEMENT_CYCLES.get((market, instrument_type))
            if by_instrument is not None:
                return by_instrument
        asset_class = self.asset_class.value if self.asset_class is not None else ""
        if market and asset_class:
            by_asset_class = _SETTLEMENT_CYCLES.get((market, asset_class))
            if by_asset_class is not None:
                return by_asset_class
        return _DEFAULT_SETTLEMENT_DAYS

    @model_validator(mode="after")
    def _validate_trade_logic(self) -> Trade:
        if self.settlement_date < self.trade_date:
            raise ValueError("settlement_date must be >= trade_date [rule: settlement_after_trade]")

        expected_days = self._expected_settlement_days()
        expected = _add_business_days(self.trade_date, expected_days)
        if self.settlement_date != expected:
            raise ValueError(
                f"Expected T+{expected_days} settlement {expected.isoformat()}, got "
                f"{self.settlement_date.isoformat()} [rule: correct_settlement_cycle]"
            )

        if self.commission is not None and self.commission.currency != self.currency:
            raise ValueError(
                "Commission currency must match trade currency [rule: commission_currency_match]"
            )

        if self.executions:
            total_filled = Decimal("0")
            for execution in self.executions:
                if execution.trade_id != self.trade_id:
                    raise ValueError(
                        "Execution trade_id must match trade_id [rule: execution_trade_link]"
                    )
                total_filled += _quantity_decimal(execution.fill_quantity)
            if total_filled > _quantity_decimal(self.quantity):
                raise ValueError(
                    "Execution fill quantities exceed trade quantity [rule: execution_quantity_limit]"
                )

        if self.allocations:
            allocation_total = Decimal("0")
            allocation_pct_total = Decimal("0")
            pct_count = 0
            for allocation in self.allocations:
                if allocation.trade_id != self.trade_id:
                    raise ValueError(
                        "Allocation trade_id must match trade_id [rule: allocation_trade_link]"
                    )
                allocation_total += _quantity_decimal(allocation.quantity)
                if allocation.allocation_pct is not None:
                    allocation_pct_total += Decimal(str(allocation.allocation_pct.as_decimal))
                    pct_count += 1
            if allocation_total != _quantity_decimal(self.quantity):
                raise ValueError(
                    "Allocation quantities must sum to trade quantity [rule: allocation_quantity_sum]"
                )
            if pct_count > 0 and abs(allocation_pct_total - Decimal("1")) > _PERCENTAGE_TOLERANCE:
                raise ValueError(
                    "Allocation percentages must sum to 100% [rule: allocation_percentage_sum]"
                )

        return self
