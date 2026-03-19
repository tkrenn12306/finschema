from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from finschema.schemas import (
    Benchmark,
    CashFlow,
    CorporateAction,
    Execution,
    Exposure,
    FundNAV,
    FXRate,
    Holding,
    Instrument,
    Order,
    Trade,
)
from finschema.types import Money


def _base_trade_kwargs() -> dict[str, object]:
    return {
        "trade_id": "T-001",
        "isin": "US0378331005",
        "side": "BUY",
        "quantity": 100,
        "price": 178.52,
        "currency": "USD",
        "trade_date": "2026-03-19",
        "settlement_date": "2026-03-20",
    }


def test_trade_eu_equity_t2_cycle_valid() -> None:
    payload = _base_trade_kwargs()
    payload["settlement_date"] = "2026-03-23"
    trade = Trade(**payload, market="EU", asset_class="EQUITY")
    assert trade.market == "EU"


def test_trade_eu_equity_t2_cycle_invalid() -> None:
    payload = _base_trade_kwargs()
    payload["settlement_date"] = "2026-03-20"
    with pytest.raises(ValidationError):
        Trade(**payload, market="EU", asset_class="EQUITY")


def test_trade_allocation_sum_rule() -> None:
    with pytest.raises(ValidationError):
        Trade(
            **_base_trade_kwargs(),
            allocations=[
                {
                    "trade_id": "T-001",
                    "portfolio_id": "P-1",
                    "quantity": 60,
                    "allocation_pct": "0.6",
                },
                {
                    "trade_id": "T-001",
                    "portfolio_id": "P-2",
                    "quantity": 30,
                    "allocation_pct": "0.3",
                },
            ],
        )


def test_trade_execution_trade_link_rule() -> None:
    with pytest.raises(ValidationError):
        Trade(
            **_base_trade_kwargs(),
            executions=[
                Execution(
                    trade_id="OTHER",
                    fill_price=178.52,
                    fill_quantity=10,
                    fill_time=datetime(2026, 3, 19, 14, 0, 0),
                    execution_venue="XNAS",
                )
            ],
        )


def test_order_limit_requires_limit_price() -> None:
    with pytest.raises(ValidationError):
        Order(
            order_id="O-1",
            isin="US0378331005",
            side="BUY",
            quantity=100,
            order_type="LIMIT",
            time_in_force="DAY",
        )


def test_holding_unrealized_pnl_consistency() -> None:
    with pytest.raises(ValidationError):
        Holding(
            portfolio_id="P-1",
            isin="US0378331005",
            quantity=10,
            market_value=Money("120", "USD"),
            cost_basis=Money("100", "USD"),
            unrealized_pnl=Money("10", "USD"),
            asset_class="EQUITY",
            as_of_date="2026-03-19",
        )


def test_exposure_consistency() -> None:
    with pytest.raises(ValidationError):
        Exposure(
            asset_class="EQUITY",
            gross_exposure=Decimal("100"),
            net_exposure=Decimal("30"),
            long_exposure=Decimal("70"),
            short_exposure=Decimal("20"),
        )


def test_benchmark_duplicate_isin_invalid() -> None:
    with pytest.raises(ValidationError):
        Benchmark(
            name="Bench",
            as_of_date="2026-03-19",
            positions=[
                {
                    "portfolio_id": "B-1",
                    "isin": "US0378331005",
                    "quantity": 10,
                    "market_value": {"amount": "100", "currency": "USD"},
                    "asset_class": "EQUITY",
                    "as_of_date": "2026-03-19",
                },
                {
                    "portfolio_id": "B-1",
                    "isin": "US0378331005",
                    "quantity": 20,
                    "market_value": {"amount": "200", "currency": "USD"},
                    "asset_class": "EQUITY",
                    "as_of_date": "2026-03-19",
                },
            ],
        )


def test_fund_nav_consistency_rule() -> None:
    with pytest.raises(ValidationError):
        FundNAV(
            fund_id="F-1",
            nav_per_share=Decimal("10"),
            total_aum=Money("2000", "USD"),
            shares_outstanding=100,
            share_class="A",
            nav_date="2026-03-19",
        )


def test_cashflow_sign_rules() -> None:
    with pytest.raises(ValidationError):
        CashFlow(
            portfolio_id="P-1",
            type="SUBSCRIPTION",
            amount=Money("-10", "USD"),
            effective_date="2026-03-19",
        )


def test_corporate_action_rules() -> None:
    with pytest.raises(ValidationError):
        CorporateAction(
            isin="US0378331005",
            action_type="SPLIT",
            ex_date="2026-03-19",
            record_date="2026-03-20",
            pay_date="2026-03-21",
            ratio=Decimal("0"),
        )


def test_fx_rate_schema_rules() -> None:
    with pytest.raises(ValidationError):
        FXRate(base="EUR", quote="EUR", rate=Decimal("1"), timestamp="2026-03-19T10:00:00")


def test_instrument_schema_valid() -> None:
    instrument = Instrument(
        isin="US0378331005",
        name="Apple Inc.",
        asset_class="EQUITY",
        currency="USD",
        exchange="XNAS",
        issue_date="2026-03-19",
    )
    assert str(instrument.exchange) == "XNAS"
