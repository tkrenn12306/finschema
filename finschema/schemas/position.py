"""Position schema for beta."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import (
    ISIN,
    AssetClass,
    BusinessDate,
    Money,
    Percentage,
    Quantity,
)


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
