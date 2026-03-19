from __future__ import annotations

from finschema.quality import Severity, ValidationEngine, rule
from finschema.schemas import Portfolio, Position, Trade
from finschema.types import NAV, Money


def make_trade(price: float = 178.52) -> Trade:
    return Trade(
        trade_id="T-001",
        isin="US0378331005",
        side="BUY",
        quantity=100,
        price=price,
        currency="USD",
        trade_date="2026-03-19",
        settlement_date="2026-03-20",
    )


def make_portfolio() -> Portfolio:
    return Portfolio(
        portfolio_id="P-001",
        name="All Weather",
        base_currency="EUR",
        positions=[
            Position(
                portfolio_id="P-001",
                isin="US0378331005",
                quantity=100,
                market_value=Money("120", "EUR"),
                weight="0.60",
                asset_class="EQUITY",
                as_of_date="2026-03-19",
            ),
            Position(
                portfolio_id="P-001",
                isin="DE000BAY0017",
                quantity=100,
                market_value=Money("70", "EUR"),
                weight="0.35",
                asset_class="EQUITY",
                as_of_date="2026-03-19",
            ),
        ],
        cash=Money("10", "EUR"),
        nav=NAV("200", "EUR", "2026-03-19"),
        as_of_date="2026-03-19",
    )


def test_validate_single_trade_report_pass() -> None:
    engine = ValidationEngine()
    report = engine.validate(make_trade(), schema="Trade")
    assert report.passed is True
    assert report.score > 0.0
    assert report.stats["total_records"] == 1


def test_price_daily_change_warning() -> None:
    engine = ValidationEngine()
    report = engine.validate(
        make_trade(price=200),
        schema="Trade",
        context={"previous_prices": {"US0378331005": "100"}},
    )
    assert any(issue.rule == "price_daily_change_limit" for issue in report.warnings)


def test_fx_rules_triggered() -> None:
    engine = ValidationEngine()
    report = engine.validate(
        {"base": "EUR", "quote": "EUR", "rate": 0},
        context={"fx_reference": {("EUR", "EUR"): 1}},
    )
    assert any(issue.rule == "fx_rate_positive" for issue in report.errors)
    assert any(issue.rule == "fx_no_self_pair" for issue in report.errors)


def test_portfolio_rules_triggered() -> None:
    engine = ValidationEngine()
    report = engine.validate(make_portfolio(), schema="Portfolio")
    assert any(issue.rule == "max_single_position" for issue in report.warnings)


def test_schema_validation_error_for_invalid_dict() -> None:
    engine = ValidationEngine()
    report = engine.validate({"trade_id": "bad"}, schema="Trade")
    assert len(report.errors) > 0
    assert any(issue.rule == "schema_validation" for issue in report.errors)


def test_engine_list_input_stats() -> None:
    engine = ValidationEngine()
    report = engine.validate([make_trade(), {"trade_id": "bad"}], schema="Trade")
    assert report.stats["total_records"] == 2
    assert report.stats["invalid"] >= 1


def test_overrides_change_rule_threshold() -> None:
    engine = ValidationEngine()
    report = engine.validate(
        make_trade(price=110),
        schema="Trade",
        context={"previous_prices": {"US0378331005": "100"}},
        overrides={"price_daily_change_max": 0.05},
    )
    assert any(issue.rule == "price_daily_change_limit" for issue in report.warnings)


def test_custom_rule_integration() -> None:
    engine = ValidationEngine()

    @rule(name="always_warn", severity=Severity.WARNING, description="test")
    def always_warn(_record: object) -> list[str]:
        return ["custom finding"]

    engine.add_rule(always_warn)
    report = engine.validate(make_trade(), schema="Trade")
    assert any(issue.rule == "always_warn" for issue in report.warnings)


def test_report_to_dict_shape() -> None:
    engine = ValidationEngine()
    report = engine.validate(make_trade(), schema="Trade")
    payload = report.to_dict()
    assert "score" in payload
    assert "stats" in payload


def test_report_to_dataframe_optional() -> None:
    engine = ValidationEngine()
    report = engine.validate(make_trade(), schema="Trade")
    try:
        df = report.to_dataframe()
        assert hasattr(df, "columns")
    except RuntimeError as exc:
        assert "pandas is not installed" in str(exc)
