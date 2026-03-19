"""Fund NAV schema."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import BusinessDate, Money, Quantity

_AUM_TOLERANCE = Decimal("0.01")


class FundNAV(BaseModel):
    fund_id: str
    nav_per_share: Decimal
    total_aum: Money
    shares_outstanding: Quantity
    share_class: str
    nav_date: BusinessDate

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_nav_logic(self) -> FundNAV:
        if self.nav_per_share <= 0:
            raise ValueError("nav_per_share must be > 0 [rule: nav_per_share_positive]")

        expected = Decimal(str(self.shares_outstanding.as_decimal)) * self.nav_per_share
        if abs(self.total_aum.amount - expected) > _AUM_TOLERANCE:
            raise ValueError(
                "total_aum must equal shares_outstanding * nav_per_share [rule: total_aum_consistency]"
            )
        return self
