"""Position, holding, and exposure schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import ISIN, AssetClass, BusinessDate, Money, Percentage, Price, Quantity

_DECIMAL_TOLERANCE = Decimal("0.01")


class Position(BaseModel):
    portfolio_id: str
    isin: ISIN
    quantity: Quantity
    market_value: Money
    cost_basis: Money | None = None
    weight: Percentage | None = None
    asset_class: AssetClass
    sector: str | None = None
    region: str | None = None
    as_of_date: BusinessDate

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_position_logic(self) -> Position:
        if self.cost_basis is not None and self.cost_basis.currency != self.market_value.currency:
            raise ValueError(
                "Cost basis currency must match market value currency "
                "[rule: cost_basis_currency_match]"
            )
        return self


class Holding(Position):
    unrealized_pnl: Money | None = None
    realized_pnl: Money | None = None
    average_cost: Price | None = None
    current_price: Price | None = None

    @model_validator(mode="after")
    def _validate_holding_logic(self) -> Holding:
        if (
            self.unrealized_pnl is not None
            and self.cost_basis is not None
            and self.unrealized_pnl.currency != self.market_value.currency
        ):
            raise ValueError(
                "unrealized_pnl currency must match market_value [rule: pnl_currency_match]"
            )

        if self.unrealized_pnl is not None and self.cost_basis is not None:
            expected = self.market_value - self.cost_basis
            if abs(expected.amount - self.unrealized_pnl.amount) > _DECIMAL_TOLERANCE:
                raise ValueError(
                    "unrealized_pnl must equal market_value - cost_basis "
                    "[rule: unrealized_pnl_consistency]"
                )
        return self


class Exposure(BaseModel):
    asset_class: AssetClass
    gross_exposure: Decimal
    net_exposure: Decimal
    long_exposure: Decimal
    short_exposure: Decimal

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_exposure_logic(self) -> Exposure:
        expected_gross = self.long_exposure + self.short_exposure
        expected_net = self.long_exposure - self.short_exposure

        if self.gross_exposure != expected_gross:
            raise ValueError(
                "gross_exposure must equal long + short [rule: exposure_gross_consistency]"
            )
        if self.net_exposure != expected_net:
            raise ValueError(
                "net_exposure must equal long - short [rule: exposure_net_consistency]"
            )
        return self
