from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from finschema.quality import ValidationEngine
from finschema.quality.engine import ValidationEngine as EngineClass
from finschema.quality.report import QualityReport, Severity, ValidationIssue
from finschema.quality.rules.portfolio_rules import validate_portfolio
from finschema.quality.rules.price_rules import validate_price
from finschema.schemas import Trade

VALID_TRADE_DICT = {
    "trade_id": "T-001",
    "isin": "US0378331005",
    "side": "BUY",
    "quantity": 100,
    "price": 178.52,
    "currency": "USD",
    "trade_date": "2026-03-19",
    "settlement_date": "2026-03-20",
}


def test_engine_normalize_tuple_input() -> None:
    engine = ValidationEngine()
    report = engine.validate((VALID_TRADE_DICT,), schema="Trade")
    assert report.stats["total_records"] == 1


def test_engine_unknown_schema_name_raises() -> None:
    engine = ValidationEngine()
    with pytest.raises(ValueError):
        engine.validate({}, schema="Unknown")


def test_engine_invalid_schema_type_raises() -> None:
    engine = ValidationEngine()
    with pytest.raises(TypeError):
        engine.validate({}, schema=123)  # type: ignore[arg-type]


def test_engine_schema_class_path() -> None:
    engine = ValidationEngine()
    report = engine.validate(VALID_TRADE_DICT, schema=Trade)
    assert report.passed is True


def test_engine_schema_unsupported_record_type() -> None:
    engine = ValidationEngine()
    report = engine.validate(123, schema="Trade")
    assert any(issue.rule == "schema_validation" for issue in report.errors)


def test_engine_custom_rule_branches() -> None:
    engine = ValidationEngine()

    def returns_false(_record: Any) -> bool:
        return False

    def returns_string(_record: Any) -> str:
        return "bad"

    def returns_set(_record: Any) -> set[str]:
        return {"a", "b"}

    def returns_object(_record: Any) -> object:
        return object()

    engine.add_rule(returns_false)
    engine.add_rule(returns_string)
    engine.add_rule(returns_set)
    engine.add_rule(returns_object)

    report = engine.validate(VALID_TRADE_DICT, schema="Trade")
    rules = {issue.rule for issue in report.errors}
    assert "returns_false" in rules
    assert "returns_string" in rules
    assert "returns_set" in rules
    assert "returns_object" in rules


def test_merge_config_nested_branch() -> None:
    merged = EngineClass._merge_config(
        {"a": {"x": 1}, "b": 2},
        {"a": {"y": 3}, "b": 4},
    )
    assert merged["a"] == {"x": 1, "y": 3}
    assert merged["b"] == 4


def test_quality_report_branches_and_grouping() -> None:
    report = QualityReport(
        issues=[
            ValidationIssue(rule="r1", severity=Severity.ERROR, message="e", record_index=None),
            ValidationIssue(
                rule="r2", severity=Severity.WARNING, message="w", field="price", record_index=1
            ),
            ValidationIssue(
                rule="r3", severity=Severity.INFO, message="i", field="price", record_index=2
            ),
        ],
        total_records=3,
        min_score=0.1,
    )

    assert len(report.issues) == 3
    assert "r1" in report.by_rule
    assert "price" in report.by_field
    assert report.stats["invalid"] == 3
    assert report.score < 1


def test_quality_report_to_dataframe_success(monkeypatch: pytest.MonkeyPatch) -> None:
    report = QualityReport(
        issues=[ValidationIssue(rule="r1", severity=Severity.ERROR, message="e")],
        total_records=1,
    )

    class FakePandas:
        pass

    def build_dataframe(rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {"rows": rows}

    FakePandas.DataFrame = staticmethod(build_dataframe)  # type: ignore[attr-defined]

    def fake_import_module(_name: str) -> Any:
        return FakePandas

    monkeypatch.setattr("finschema.quality.report.importlib.import_module", fake_import_module)
    payload = report.to_dataframe()
    assert payload["rows"][0]["rule"] == "r1"


def test_price_rule_direct_branches() -> None:
    issues_no_price = validate_price({}, record_index=0, config={}, context={})
    assert issues_no_price == []

    record = {
        "isin": "US0378331005",
        "price": Decimal("400"),
        "asset_class": "FIXED_INCOME",
    }
    issues = validate_price(
        record,
        record_index=0,
        config={
            "price_min": Decimal("0"),
            "price_max_by_asset_class": {"FIXED_INCOME": Decimal("300")},
            "price_daily_change_max": Decimal("0.10"),
        },
        context={"previous_prices": {"US0378331005": Decimal("100")}},
    )
    rules = {issue.rule for issue in issues}
    assert "price_within_bounds" in rules
    assert "price_daily_change_limit" in rules


def test_price_rule_as_decimal_value_branches() -> None:
    class HasAsDecimal:
        as_decimal = Decimal("1")

    class HasValue:
        value = Decimal("1")

    issues_a = validate_price(
        {"price": HasAsDecimal()},
        record_index=0,
        config={"price_min": Decimal("0")},
        context={},
    )
    issues_b = validate_price(
        {"price": HasValue()},
        record_index=0,
        config={"price_min": Decimal("0")},
        context={},
    )
    assert issues_a == []
    assert issues_b == []


def test_portfolio_rule_direct_branches() -> None:
    assert validate_portfolio({}, record_index=0, config={}, context={}) == []

    record_missing_nav = {"positions": [], "cash": {"amount": "1", "currency": "EUR"}}
    assert validate_portfolio(record_missing_nav, record_index=0, config={}, context={}) == []

    record_nav_negative = {
        "base_currency": "EUR",
        "positions": [],
        "cash": {"amount": "1", "currency": "EUR"},
        "nav": {"amount": "0", "currency": "EUR"},
    }
    issues_nav = validate_portfolio(record_nav_negative, record_index=0, config={}, context={})
    assert any(issue.rule == "nav_positive" for issue in issues_nav)

    complex_record = {
        "base_currency": "EUR",
        "positions": [
            {"isin": "AAA", "market_value": {"amount": "120", "currency": "USD"}},
            {"isin": "AAA", "market_value": {"amount": "70", "currency": "EUR"}, "weight": "0.35"},
        ],
        "cash": {"amount": "10", "currency": "USD"},
        "nav": {"amount": "200", "currency": "USD"},
    }
    issues_complex = validate_portfolio(
        complex_record,
        record_index=0,
        config={"weight_tolerance": 0.001, "max_single_position": 0.25},
        context={},
    )
    rules = {issue.rule for issue in issues_complex}
    assert "no_duplicate_positions" in rules
    assert "currency_consistent" in rules
    assert "max_single_position" in rules
