from __future__ import annotations

import pytest
from pydantic import ValidationError

from finschema.schemas import Portfolio, Position
from finschema.types import NAV, Money


def test_portfolio_currency_mismatch_invalid() -> None:
    with pytest.raises(ValidationError):
        Portfolio(
            portfolio_id="P-001",
            name="Mismatch",
            base_currency="EUR",
            positions=[
                Position(
                    portfolio_id="P-001",
                    isin="US0378331005",
                    quantity=100,
                    market_value=Money("90", "EUR"),
                    asset_class="EQUITY",
                    as_of_date="2026-03-19",
                )
            ],
            cash=Money("10", "USD"),
            nav=NAV("100", "USD", "2026-03-19"),
            as_of_date="2026-03-19",
        )


def test_portfolio_position_date_mismatch_invalid() -> None:
    with pytest.raises(ValidationError):
        Portfolio(
            portfolio_id="P-001",
            name="Date Mismatch",
            base_currency="EUR",
            positions=[
                Position(
                    portfolio_id="P-001",
                    isin="US0378331005",
                    quantity=100,
                    market_value=Money("90", "EUR"),
                    asset_class="EQUITY",
                    as_of_date="2026-03-20",
                )
            ],
            cash=Money("10", "EUR"),
            nav=NAV("100", "EUR", "2026-03-19"),
            as_of_date="2026-03-19",
        )


def test_portfolio_weight_fallback_without_explicit_weight() -> None:
    portfolio = Portfolio(
        portfolio_id="P-001",
        name="Fallback Weight",
        base_currency="EUR",
        positions=[
            Position(
                portfolio_id="P-001",
                isin="US0378331005",
                quantity=100,
                market_value=Money("90", "EUR"),
                weight="0.45",
                asset_class="EQUITY",
                as_of_date="2026-03-19",
            ),
            Position(
                portfolio_id="P-001",
                isin="DE000BAY0017",
                quantity=100,
                market_value=Money("100", "EUR"),
                asset_class="EQUITY",
                as_of_date="2026-03-19",
            ),
        ],
        cash=Money("10", "EUR"),
        nav=NAV("200", "EUR", "2026-03-19"),
        as_of_date="2026-03-19",
    )
    assert portfolio.portfolio_id == "P-001"
