"""FX rate schema."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from finschema.types import CurrencyCode


class FXRate(BaseModel):
    base: CurrencyCode
    quote: CurrencyCode
    rate: Decimal
    timestamp: datetime

    model_config = ConfigDict(validate_assignment=True)

    @model_validator(mode="after")
    def _validate_rate_logic(self) -> FXRate:
        if self.base == self.quote:
            raise ValueError("base and quote must differ [rule: fx_no_self_pair]")
        if self.rate <= 0:
            raise ValueError("rate must be > 0 [rule: fx_rate_positive]")
        return self
