"""Instrument schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from finschema.types import ISIN, MIC, AssetClass, BusinessDate, CurrencyCode


class Instrument(BaseModel):
    isin: ISIN
    name: str
    asset_class: AssetClass
    currency: CurrencyCode
    exchange: MIC | None = None
    issue_date: BusinessDate

    model_config = ConfigDict(validate_assignment=True)


class Equity(Instrument):
    pass


class Bond(Instrument):
    pass


class Option(Instrument):
    pass


class Future(Instrument):
    pass


class Fund(Instrument):
    pass
