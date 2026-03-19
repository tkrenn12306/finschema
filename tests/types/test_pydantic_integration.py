from __future__ import annotations

from pydantic import BaseModel

from finschema.types import ISIN, BusinessDate, Money


class TradeModel(BaseModel):
    isin: ISIN
    trade_date: BusinessDate
    notional: Money


def test_pydantic_parsing() -> None:
    model = TradeModel(
        isin="US0378331005",
        trade_date="2026-03-19",
        notional={"amount": "100.00", "currency": "EUR"},
    )
    assert str(model.isin) == "US0378331005"
    assert model.trade_date.isoformat() == "2026-03-19"
    assert str(model.notional.currency) == "EUR"
