"""Cash flow schema."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import BusinessDate, CashFlowType, Money


class CashFlow(BaseModel):
    portfolio_id: str
    type: CashFlowType
    amount: Money
    effective_date: BusinessDate

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_cashflow_signs(self) -> CashFlow:
        if self.type == CashFlowType.SUBSCRIPTION and self.amount.amount <= 0:
            raise ValueError("SUBSCRIPTION amount must be positive [rule: cashflow_sign]")
        if self.type in {CashFlowType.REDEMPTION, CashFlowType.FEE} and self.amount.amount >= 0:
            raise ValueError(f"{self.type.value} amount must be negative [rule: cashflow_sign]")
        return self
