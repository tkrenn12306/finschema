from __future__ import annotations

from pathlib import Path

import pytest

from finschema.errors import ValidationError
from finschema.quality import RuleSet, Severity, ValidationEngine, rule

VALID_TRADE = {
    "trade_id": "T-001",
    "isin": "US0378331005",
    "side": "BUY",
    "quantity": 100,
    "price": 178.52,
    "currency": "USD",
    "trade_date": "2026-03-19",
    "settlement_date": "2026-03-20",
}

VALID_POSITION = {
    "portfolio_id": "P-001",
    "isin": "US0378331005",
    "quantity": 100,
    "market_value": {"amount": "90", "currency": "USD"},
    "asset_class": "EQUITY",
    "as_of_date": "2026-03-19",
}


def test_engine_init_invalid_config_key_raises() -> None:
    with pytest.raises(ValidationError):
        ValidationEngine(config={"unknown_key": 1})


def test_engine_config_load_from_toml_file(tmp_path: Path) -> None:
    config_file = tmp_path / "finschema.toml"
    config_file.write_text(
        "min_score = 0.88\nweight_tolerance = 0.002\n[price_max_by_asset_class]\nEQUITY = 123456\n",
        encoding="utf-8",
    )

    engine = ValidationEngine(config=config_file)
    assert float(engine.config["min_score"]) == pytest.approx(0.88)
    assert str(engine.config["price_max_by_asset_class"]["EQUITY"]) == "123456"


def test_engine_auto_load_pyproject_tool_section(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        "[tool.finschema]\nmin_score = 0.91\nstrict_mode = false\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    engine = ValidationEngine()
    assert float(engine.config["min_score"]) == pytest.approx(0.91)


def test_validate_overrides_invalid_key_raises() -> None:
    engine = ValidationEngine()
    with pytest.raises(ValidationError):
        engine.validate(VALID_TRADE, schema="Trade", overrides={"invalid_key": 1})


def test_rule_applies_to_filters_execution() -> None:
    engine = ValidationEngine()

    @rule(name="trade_only_rule", severity=Severity.ERROR, applies_to=["Trade"])
    def trade_only_rule(_record: object) -> list[str]:
        return ["trade-only finding"]

    engine.add_rule(trade_only_rule)

    report_trade = engine.validate(VALID_TRADE, schema="Trade")
    report_position = engine.validate(VALID_POSITION, schema="Position")

    assert any(issue.rule == "trade_only_rule" for issue in report_trade.errors)
    assert all(issue.rule != "trade_only_rule" for issue in report_position.errors)


def test_strict_mode_raises_on_first_error() -> None:
    engine = ValidationEngine(strict_mode=True)
    with pytest.raises(ValidationError):
        engine.validate({"trade_id": "bad"}, schema="Trade")


def test_ruleset_enable_disable_behavior() -> None:
    engine = ValidationEngine()
    report = engine.validate(
        VALID_TRADE,
        schema="Trade",
        context={"previous_prices": {"US0378331005": "100"}},
        overrides={"enabled_rulesets": ["identifier"]},
    )
    assert all(issue.rule in {"check_digit_valid", "format_valid"} for issue in report.issues)


def test_identifier_builtin_rules_without_schema() -> None:
    engine = ValidationEngine()
    report = engine.validate({"isin": "US0378331009"})
    assert any(issue.rule == "check_digit_valid" for issue in report.errors)


def test_stale_price_detection_rule() -> None:
    engine = ValidationEngine()
    report = engine.validate(
        VALID_TRADE,
        schema="Trade",
        context={"stale_price_days_by_isin": {"US0378331005": 4}},
    )
    assert any(issue.rule == "stale_price_detection" for issue in report.warnings)


def test_custom_ruleset_registration() -> None:
    engine = ValidationEngine()
    engine.add_ruleset(RuleSet(name="custom", rules=("always_warn",)))

    @rule(name="always_warn", severity=Severity.WARNING)
    def always_warn(_record: object) -> list[str]:
        return ["warn"]

    engine.add_rule(always_warn)
    report = engine.validate(
        VALID_TRADE,
        schema="Trade",
        overrides={"enabled_rulesets": ["custom"]},
    )
    assert len(report.warnings) == 1
