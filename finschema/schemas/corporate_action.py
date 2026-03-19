"""Corporate action schema."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import ISIN, BusinessDate, CorporateActionType, Money


class CorporateAction(BaseModel):
    isin: ISIN
    action_type: CorporateActionType
    ex_date: BusinessDate
    record_date: BusinessDate
    pay_date: BusinessDate
    ratio: Decimal | None = None
    amount: Money | None = None

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_action_logic(self) -> CorporateAction:
        if not (self.ex_date <= self.record_date <= self.pay_date):
            raise ValueError("ex_date must be <= record_date <= pay_date [rule: action_date_order]")

        if self.action_type in {CorporateActionType.SPLIT, CorporateActionType.REVERSE_SPLIT} and (
            self.ratio is None or self.ratio <= 0
        ):
            raise ValueError("ratio must be > 0 for split actions [rule: action_ratio_positive]")

        if self.action_type in {
            CorporateActionType.CASH_DIVIDEND,
            CorporateActionType.STOCK_DIVIDEND,
        } and (self.amount is None or self.amount.amount <= 0):
            raise ValueError(
                "amount must be > 0 for dividend actions [rule: action_amount_positive]"
            )

        return self
