"""Portfolio schema for beta."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import NAV, BusinessDate, CurrencyCode, Money

from .position import Position


class Portfolio(BaseModel):
    portfolio_id: str
    name: str
    base_currency: CurrencyCode
    positions: list[Position]
    cash: Money
    nav: NAV
    as_of_date: BusinessDate

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_portfolio_logic(self) -> Portfolio:
        errors: list[str] = []

        if self.cash.currency != self.base_currency:
            errors.append("Cash currency must match base_currency [rule: currency_consistent]")

        if self.nav.currency != self.base_currency:
            errors.append("NAV currency must match base_currency [rule: currency_consistent]")

        seen_isins: set[str] = set()
        for position in self.positions:
            isin_key = str(position.isin)
            if isin_key in seen_isins:
                errors.append("Duplicate ISIN found in positions [rule: no_duplicate_isins]")
                break
            seen_isins.add(isin_key)

        for position in self.positions:
            if position.as_of_date != self.as_of_date:
                errors.append(
                    "All position dates must match portfolio as_of_date [rule: aligned_as_of_date]"
                )
                break

        for position in self.positions:
            if position.market_value.currency != self.base_currency:
                errors.append(
                    "Position market value currency must match base_currency "
                    "[rule: currency_consistent]"
                )
                break

        nav_amount = self.nav.amount
        calculated_total = (
            sum((position.market_value.amount for position in self.positions), Decimal("0"))
            + self.cash.amount
        )
        nav_tolerance = Decimal("0.01")
        if abs(calculated_total - nav_amount) > nav_tolerance:
            errors.append("Sum(market_values)+cash must match NAV [rule: nav_consistency]")

        weight_tolerance = Decimal("0.001")
        position_weight_sum = Decimal("0")
        if nav_amount > 0:
            for position in self.positions:
                if position.weight is not None:
                    position_weight_sum += position.weight.as_decimal
                else:
                    position_weight_sum += position.market_value.amount / nav_amount
            cash_weight = self.cash.amount / nav_amount
            total_weight = position_weight_sum + cash_weight
            if abs(total_weight - Decimal("1")) > weight_tolerance:
                errors.append(
                    "Portfolio weights must sum to 100% (including cash) [rule: weights_sum_to_one]"
                )

        if errors:
            raise ValueError(" | ".join(errors))

        return self
