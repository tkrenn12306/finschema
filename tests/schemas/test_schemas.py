from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from finschema.schemas import Portfolio, Position, Trade
from finschema.types import NAV, Money


def make_position(isin: str, mv: str, weight: str) -> Position:
    return Position(
        portfolio_id="P-001",
        isin=isin,
        quantity=100,
        market_value=Money(mv, "EUR"),
        cost_basis=Money(mv, "EUR"),
        weight=weight,
        asset_class="EQUITY",
        as_of_date="2026-03-19",
    )


def test_trade_valid() -> None:
    trade = Trade(
        trade_id="T-001",
        isin="US0378331005",
        side="BUY",
        quantity=100,
        price=178.52,
        currency="USD",
        trade_date="2026-03-19",
        settlement_date="2026-03-20",
    )
    assert str(trade.isin) == "US0378331005"


def test_trade_settlement_before_trade_invalid() -> None:
    with pytest.raises(ValidationError):
        Trade(
            trade_id="T-001",
            isin="US0378331005",
            side="BUY",
            quantity=100,
            price=178.52,
            currency="USD",
            trade_date="2026-03-19",
            settlement_date="2026-03-18",
        )


def test_trade_wrong_t_plus_one_invalid() -> None:
    with pytest.raises(ValidationError):
        Trade(
            trade_id="T-001",
            isin="US0378331005",
            side="BUY",
            quantity=100,
            price=178.52,
            currency="USD",
            trade_date="2026-03-19",
            settlement_date="2026-03-24",
        )


def test_trade_commission_currency_mismatch_invalid() -> None:
    with pytest.raises(ValidationError):
        Trade(
            trade_id="T-001",
            isin="US0378331005",
            side="BUY",
            quantity=100,
            price=178.52,
            currency="USD",
            trade_date="2026-03-19",
            settlement_date="2026-03-20",
            commission=Money("10", "EUR"),
        )


def test_position_cost_basis_currency_mismatch_invalid() -> None:
    with pytest.raises(ValidationError):
        Position(
            portfolio_id="P-001",
            isin="US0378331005",
            quantity=100,
            market_value=Money("90", "EUR"),
            cost_basis=Money("80", "USD"),
            weight="0.45",
            asset_class="EQUITY",
            as_of_date="2026-03-19",
        )


def test_portfolio_valid() -> None:
    portfolio = Portfolio(
        portfolio_id="P-001",
        name="All Weather",
        base_currency="EUR",
        positions=[
            make_position("US0378331005", "90", "0.45"),
            make_position("DE000BAY0017", "100", "0.50"),
        ],
        cash=Money("10", "EUR"),
        nav=NAV("200", "EUR", "2026-03-19"),
        as_of_date="2026-03-19",
    )
    assert portfolio.nav.amount == Decimal("200")


def test_portfolio_duplicate_isin_invalid() -> None:
    with pytest.raises(ValidationError):
        Portfolio(
            portfolio_id="P-001",
            name="All Weather",
            base_currency="EUR",
            positions=[
                make_position("US0378331005", "90", "0.45"),
                make_position("US0378331005", "100", "0.50"),
            ],
            cash=Money("10", "EUR"),
            nav=NAV("200", "EUR", "2026-03-19"),
            as_of_date="2026-03-19",
        )


def test_portfolio_nav_inconsistent_invalid() -> None:
    with pytest.raises(ValidationError):
        Portfolio(
            portfolio_id="P-001",
            name="All Weather",
            base_currency="EUR",
            positions=[
                make_position("US0378331005", "90", "0.45"),
                make_position("DE000BAY0017", "100", "0.50"),
            ],
            cash=Money("10", "EUR"),
            nav=NAV("250", "EUR", "2026-03-19"),
            as_of_date="2026-03-19",
        )
