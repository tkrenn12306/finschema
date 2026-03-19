"""Validation engine for beta quality checks."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from finschema.quality.decorators import get_rule_metadata
from finschema.quality.report import QualityReport, Severity, ValidationIssue
from finschema.quality.rules.fx_rules import validate_fx
from finschema.quality.rules.portfolio_rules import validate_portfolio
from finschema.quality.rules.price_rules import validate_price


class ValidationEngine:
    DEFAULT_CONFIG: dict[str, Any] = {
        "weight_tolerance": Decimal("0.001"),
        "max_single_position": Decimal("0.25"),
        "fx_deviation_max": Decimal("0.05"),
        "fx_inverse_tolerance": Decimal("0.02"),
        "price_min": Decimal("0"),
        "price_daily_change_max": Decimal("0.25"),
        "price_max_by_asset_class": {
            "EQUITY": Decimal("999999"),
            "FIXED_INCOME": Decimal("300"),
            "FX": Decimal("10"),
            "COMMODITY": Decimal("1000000"),
            "DERIVATIVE": Decimal("1000000"),
        },
        "min_score": 0.95,
        "strict_mode": False,
    }

    def __init__(self, config: dict[str, Any] | None = None, strict_mode: bool = False):
        merged = self._merge_config(self.DEFAULT_CONFIG, config or {})
        merged["strict_mode"] = strict_mode
        self._config = merged
        self._custom_rules: list[Callable[..., Any]] = []

    def add_rule(self, rule_func: Callable[..., Any]) -> None:
        self._custom_rules.append(rule_func)

    def validate(
        self,
        data: Any,
        schema: type[BaseModel] | str | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> QualityReport:
        records = self._normalize_records(data)
        schema_type = self._resolve_schema(schema)
        runtime_config = self._merge_config(self._config, overrides or {})
        runtime_context = context or {}

        issues: list[ValidationIssue] = []

        for index, record in enumerate(records):
            parsed = self._coerce_record(record, schema_type, index, issues)
            if parsed is None:
                continue

            issues.extend(
                validate_price(
                    parsed,
                    record_index=index,
                    config=runtime_config,
                    context=runtime_context,
                )
            )
            issues.extend(
                validate_fx(
                    parsed,
                    record_index=index,
                    config=runtime_config,
                    context=runtime_context,
                )
            )
            issues.extend(
                validate_portfolio(
                    parsed,
                    record_index=index,
                    config=runtime_config,
                    context=runtime_context,
                )
            )
            issues.extend(self._run_custom_rules(parsed, index))

        return QualityReport(
            issues=issues,
            total_records=len(records),
            min_score=float(runtime_config.get("min_score", 0.95)),
        )

    @staticmethod
    def _normalize_records(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, tuple):
            return list(data)
        return [data]

    @staticmethod
    def _merge_config(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        merged: dict[str, Any] = dict(base)
        for key, value in override.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                current = dict(merged[key])
                current.update(value)
                merged[key] = current
            else:
                merged[key] = value
        return merged

    def _resolve_schema(self, schema: type[BaseModel] | str | None) -> type[BaseModel] | None:
        if schema is None:
            return None

        if isinstance(schema, str):
            from finschema.schemas import Portfolio, Position, Trade

            known: dict[str, type[BaseModel]] = {
                "Trade": Trade,
                "Position": Position,
                "Portfolio": Portfolio,
            }
            resolved = known.get(schema)
            if resolved is None:
                raise ValueError(f"Unknown schema name: {schema}")
            return resolved

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema

        raise TypeError("schema must be None, a schema name, or a Pydantic BaseModel type")

    @staticmethod
    def _coerce_record(
        record: Any,
        schema_type: type[BaseModel] | None,
        index: int,
        issues: list[ValidationIssue],
    ) -> Any | None:
        if schema_type is None:
            return record

        if isinstance(record, schema_type):
            return record

        if isinstance(record, dict):
            try:
                return schema_type.model_validate(record)
            except PydanticValidationError as exc:
                for error in exc.errors():
                    loc = ".".join(str(part) for part in error.get("loc", ())) or "__root__"
                    issues.append(
                        ValidationIssue(
                            rule="schema_validation",
                            severity=Severity.ERROR,
                            message=str(error.get("msg", "schema validation error")),
                            field=loc,
                            record_index=index,
                            context={"type": str(error.get("type", "unknown"))},
                        )
                    )
                return None

        issues.append(
            ValidationIssue(
                rule="schema_validation",
                severity=Severity.ERROR,
                message=(
                    f"Record type {type(record).__name__} is not supported for schema "
                    f"{schema_type.__name__}"
                ),
                field="__root__",
                record_index=index,
            )
        )
        return None

    def _run_custom_rules(self, record: Any, record_index: int) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        for custom_rule in self._custom_rules:
            metadata = get_rule_metadata(custom_rule)
            name = metadata.name if metadata else custom_rule.__name__
            severity = metadata.severity if metadata else Severity.ERROR
            description = metadata.description if metadata else ""

            try:
                result = custom_rule(record)
            except Exception as exc:  # pragma: no cover - defensive path
                issues.append(
                    ValidationIssue(
                        rule=name,
                        severity=Severity.ERROR,
                        message=f"Rule execution failed: {exc}",
                        field="__root__",
                        record_index=record_index,
                    )
                )
                continue

            messages: list[str] = []
            if result is None or result is True:
                continue
            if result is False:
                messages = ["Rule returned False"]
            elif isinstance(result, str):
                messages = [result]
            elif isinstance(result, (list, tuple, set)):
                messages = [str(item) for item in result if str(item)]
            else:
                messages = [f"Unsupported custom rule return type: {type(result).__name__}"]

            for message in messages:
                issue_context: dict[str, Any] = {}
                if description:
                    issue_context["description"] = description
                issues.append(
                    ValidationIssue(
                        rule=name,
                        severity=severity,
                        message=message,
                        field="__root__",
                        record_index=record_index,
                        context=issue_context,
                    )
                )

        return issues
