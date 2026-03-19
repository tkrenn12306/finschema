"""Validation engine for quality checks."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import ValidationError
from finschema.quality.config import load_engine_config, validate_engine_config
from finschema.quality.decorators import get_rule_metadata
from finschema.quality.report import QualityReport, Severity, ValidationIssue
from finschema.quality.rules.fx_rules import validate_fx
from finschema.quality.rules.identifier_rules import validate_identifiers
from finschema.quality.rules.portfolio_rules import validate_portfolio
from finschema.quality.rules.price_rules import validate_price


@dataclass(frozen=True, slots=True)
class RuleSet:
    name: str
    rules: tuple[str, ...]


def _default_rulesets() -> dict[str, RuleSet]:
    return {
        "identifier": RuleSet("identifier", ("check_digit_valid", "format_valid")),
        "price": RuleSet(
            "price",
            (
                "positive_price",
                "price_within_bounds",
                "price_daily_change_limit",
                "stale_price_detection",
            ),
        ),
        "fx": RuleSet(
            "fx",
            (
                "fx_rate_positive",
                "fx_no_self_pair",
                "fx_deviation_limit",
                "fx_inverse_consistency",
            ),
        ),
        "portfolio": RuleSet(
            "portfolio",
            (
                "weights_sum_to_one",
                "max_single_position",
                "no_duplicate_positions",
                "currency_consistent",
                "nav_consistency",
                "nav_positive",
            ),
        ),
    }


class ValidationEngine:
    def __init__(
        self,
        config: dict[str, Any] | str | Path | None = None,
        strict_mode: bool | None = None,
    ):
        resolved = load_engine_config(config)
        if strict_mode is not None:
            resolved["strict_mode"] = strict_mode
        self._config = resolved
        self._custom_rules: list[Callable[..., Any]] = []
        self._rulesets: dict[str, RuleSet] = _default_rulesets()

    @property
    def config(self) -> dict[str, Any]:
        return dict(self._config)

    def add_rule(self, rule_func: Callable[..., Any]) -> None:
        self._custom_rules.append(rule_func)

    def add_ruleset(self, ruleset: RuleSet) -> None:
        self._rulesets[ruleset.name.lower()] = ruleset

    def validate(
        self,
        data: Any,
        schema: type[BaseModel] | str | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> QualityReport:
        records = self._normalize_records(data)
        schema_type = self._resolve_schema(schema)
        schema_name = schema_type.__name__ if schema_type is not None else None
        runtime_config = validate_engine_config(self._merge_config(self._config, overrides or {}))
        runtime_context = context or {}
        strict_mode = bool(runtime_config.get("strict_mode", False))

        issues: list[ValidationIssue] = []

        checks_per_record = self._estimated_checks_per_record(runtime_config)
        total_checks = max(1, len(records) * checks_per_record)

        for index, record in enumerate(records):
            parsed = self._coerce_record(record, schema_type, index, issues, strict_mode)
            if parsed is None:
                continue

            built_in_issues = self._run_builtin_rules(
                parsed,
                record_index=index,
                config=runtime_config,
                context=runtime_context,
            )
            for issue in built_in_issues:
                if self._is_rule_enabled(issue.rule, runtime_config):
                    issues.append(issue)
                    if strict_mode and issue.severity == Severity.ERROR:
                        self._raise_strict_issue(issue)

            custom_issues = self._run_custom_rules(
                parsed,
                record_index=index,
                schema_name=schema_name,
            )
            for issue in custom_issues:
                if self._is_rule_enabled(issue.rule, runtime_config):
                    issues.append(issue)
                    if strict_mode and issue.severity == Severity.ERROR:
                        self._raise_strict_issue(issue)

        return QualityReport(
            issues=issues,
            total_records=len(records),
            min_score=float(runtime_config.get("min_score", 0.95)),
            total_checks=total_checks,
            fail_on_severity=str(runtime_config.get("fail_on_severity", "ERROR")),
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
                nested = dict(merged[key])
                nested.update(value)
                merged[key] = nested
            else:
                merged[key] = value
        return merged

    def _resolve_schema(self, schema: type[BaseModel] | str | None) -> type[BaseModel] | None:
        if schema is None:
            return None

        if isinstance(schema, str):
            from finschema import schemas as schemas_module

            candidate = getattr(schemas_module, schema, None)
            if isinstance(candidate, type) and issubclass(candidate, BaseModel):
                return candidate
            raise ValueError(f"Unknown schema name: {schema}")

        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema

        raise TypeError("schema must be None, a schema name, or a Pydantic BaseModel type")

    @staticmethod
    def _coerce_record(
        record: Any,
        schema_type: type[BaseModel] | None,
        index: int,
        issues: list[ValidationIssue],
        strict_mode: bool,
    ) -> Any | None:
        if schema_type is None:
            return record

        if isinstance(record, schema_type):
            return record

        if isinstance(record, dict):
            try:
                return schema_type.model_validate(record)
            except PydanticValidationError as exc:
                first_issue: ValidationIssue | None = None
                for error in exc.errors():
                    loc = ".".join(str(part) for part in error.get("loc", ())) or "__root__"
                    issue = ValidationIssue(
                        rule="schema_validation",
                        severity=Severity.ERROR,
                        message=str(error.get("msg", "schema validation error")),
                        field=loc,
                        record_index=index,
                        context={"type": str(error.get("type", "unknown"))},
                    )
                    if first_issue is None:
                        first_issue = issue
                    issues.append(issue)
                if strict_mode and first_issue is not None:
                    ValidationEngine._raise_strict_issue(first_issue)
                return None

        issue = ValidationIssue(
            rule="schema_validation",
            severity=Severity.ERROR,
            message=(
                f"Record type {type(record).__name__} is not supported for schema "
                f"{schema_type.__name__}"
            ),
            field="__root__",
            record_index=index,
        )
        issues.append(issue)
        if strict_mode:
            ValidationEngine._raise_strict_issue(issue)
        return None

    @staticmethod
    def _run_builtin_rules(
        record: Any,
        *,
        record_index: int,
        config: dict[str, Any],
        context: dict[str, Any],
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        issues.extend(
            validate_identifiers(
                record,
                record_index=record_index,
                config=config,
                context=context,
            )
        )
        issues.extend(
            validate_price(
                record,
                record_index=record_index,
                config=config,
                context=context,
            )
        )
        issues.extend(
            validate_fx(
                record,
                record_index=record_index,
                config=config,
                context=context,
            )
        )
        issues.extend(
            validate_portfolio(
                record,
                record_index=record_index,
                config=config,
                context=context,
            )
        )
        return issues

    def _run_custom_rules(
        self,
        record: Any,
        *,
        record_index: int,
        schema_name: str | None,
    ) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []

        for custom_rule in self._custom_rules:
            metadata = get_rule_metadata(custom_rule)
            name = metadata.name if metadata else custom_rule.__name__
            severity = metadata.severity if metadata else Severity.ERROR
            description = metadata.description if metadata else ""

            if (
                metadata
                and metadata.applies_to
                and schema_name is not None
                and schema_name not in metadata.applies_to
            ):
                continue

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

            if isinstance(result, ValidationIssue):
                issues.append(
                    ValidationIssue(
                        rule=result.rule,
                        severity=result.severity,
                        message=result.message,
                        field=result.field,
                        record_index=record_index
                        if result.record_index is None
                        else result.record_index,
                        context=dict(result.context),
                    )
                )
                continue

            if (
                isinstance(result, list)
                and result
                and all(isinstance(item, ValidationIssue) for item in result)
            ):
                typed_result = [item for item in result if isinstance(item, ValidationIssue)]
                for item in typed_result:
                    issues.append(
                        ValidationIssue(
                            rule=item.rule,
                            severity=item.severity,
                            message=item.message,
                            field=item.field,
                            record_index=record_index
                            if item.record_index is None
                            else item.record_index,
                            context=dict(item.context),
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

    def _is_rule_enabled(self, rule_name: str, config: dict[str, Any]) -> bool:
        enabled_rules = {str(item) for item in config.get("enabled_rules", [])}
        disabled_rules = {str(item) for item in config.get("disabled_rules", [])}
        if rule_name in disabled_rules:
            return False
        if enabled_rules and rule_name not in enabled_rules:
            return False

        enabled_rulesets = [str(item).lower() for item in config.get("enabled_rulesets", [])]
        disabled_rulesets = [str(item).lower() for item in config.get("disabled_rulesets", [])]

        if enabled_rulesets:
            allowed_by_set: set[str] = set()
            for ruleset_name in enabled_rulesets:
                ruleset = self._rulesets.get(ruleset_name)
                if ruleset is not None:
                    allowed_by_set.update(ruleset.rules)
            if allowed_by_set and rule_name not in allowed_by_set:
                return False

        for ruleset_name in disabled_rulesets:
            ruleset = self._rulesets.get(ruleset_name)
            if ruleset is not None and rule_name in ruleset.rules:
                return False

        return True

    def _estimated_checks_per_record(self, config: dict[str, Any]) -> int:
        built_in = 4
        custom = len(self._custom_rules)
        if config.get("enabled_rulesets"):
            built_in = 0
            for ruleset_name in config.get("enabled_rulesets", []):
                ruleset = self._rulesets.get(str(ruleset_name).lower())
                if ruleset is not None:
                    built_in += len(ruleset.rules)
            built_in = max(1, built_in)
        return max(1, built_in + custom)

    @staticmethod
    def _raise_strict_issue(issue: ValidationIssue) -> None:
        raise ValidationError(
            issue.message,
            field=issue.field,
            actual=issue.context,
            details={
                "rule": issue.rule,
                "record_index": issue.record_index,
                "severity": issue.severity.value,
            },
        )
