"""Trade schema for beta."""

from __future__ import annotations

from datetime import date, timedelta

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import ISIN, LEI, BusinessDate, CurrencyCode, Money, Price, Quantity, Side


def _next_business_day(value: date) -> BusinessDate:
    next_day = value + timedelta(days=1)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return BusinessDate(next_day)


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
    venue: str | None = None
    commission: Money | None = None

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_trade_logic(self) -> Trade:
        if self.settlement_date < self.trade_date:
            raise ValueError("Settlement date is before trade date [rule: settlement_after_trade]")

        expected = _next_business_day(self.trade_date)
        if self.settlement_date != expected:
            raise ValueError(
                f"Expected T+1 settlement {expected.isoformat()}, got "
                f"{self.settlement_date.isoformat()} [rule: correct_settlement_cycle]"
            )

        if self.commission is not None and self.commission.currency != self.currency:
            raise ValueError(
                "Commission currency must match trade currency [rule: commission_currency_match]"
            )

        return self
