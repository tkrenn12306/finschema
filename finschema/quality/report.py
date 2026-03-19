"""Quality report data structures."""

from __future__ import annotations

import importlib
from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    rule: str
    severity: Severity
    message: str
    field: str | None = None
    record_index: int | None = None
    context: dict[str, Any] = dataclass_field(default_factory=dict)


class QualityReport:
    def __init__(self, issues: list[ValidationIssue], total_records: int, min_score: float = 0.95):
        self._issues = list(issues)
        self._total_records = max(0, total_records)
        self._min_score = min_score

    @property
    def issues(self) -> list[ValidationIssue]:
        return list(self._issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self._issues if issue.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self._issues if issue.severity == Severity.WARNING]

    @property
    def info(self) -> list[ValidationIssue]:
        return [issue for issue in self._issues if issue.severity == Severity.INFO]

    @property
    def by_rule(self) -> dict[str, list[ValidationIssue]]:
        grouped: dict[str, list[ValidationIssue]] = defaultdict(list)
        for issue in self._issues:
            grouped[issue.rule].append(issue)
        return dict(grouped)

    @property
    def by_field(self) -> dict[str, list[ValidationIssue]]:
        grouped: dict[str, list[ValidationIssue]] = defaultdict(list)
        for issue in self._issues:
            grouped[issue.field or "__root__"].append(issue)
        return dict(grouped)

    @property
    def score(self) -> float:
        denominator = max(self._total_records, 1)
        penalties = len(self.errors) * 1.0 + len(self.warnings) * 0.25 + len(self.info) * 0.05
        return max(0.0, 1.0 - penalties / float(denominator))

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0 and self.score >= self._min_score

    @property
    def stats(self) -> dict[str, float | int]:
        invalid = self._compute_invalid_record_count()
        valid = max(0, self._total_records - invalid)
        error_rate = float(invalid) / float(self._total_records) if self._total_records else 0.0
        return {
            "total_records": self._total_records,
            "valid": valid,
            "invalid": invalid,
            "error_rate": error_rate,
        }

    def _compute_invalid_record_count(self) -> int:
        if self._total_records == 0:
            return 0

        indexed_errors = {
            issue.record_index for issue in self.errors if issue.record_index is not None
        }
        has_global_error = any(issue.record_index is None for issue in self.errors)

        if self._total_records == 1 and (indexed_errors or has_global_error):
            return 1

        if indexed_errors:
            return len(indexed_errors)

        if has_global_error:
            return self._total_records

        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "passed": self.passed,
            "stats": self.stats,
            "errors": [self._issue_to_dict(issue) for issue in self.errors],
            "warnings": [self._issue_to_dict(issue) for issue in self.warnings],
            "info": [self._issue_to_dict(issue) for issue in self.info],
            "by_rule": {
                rule: [self._issue_to_dict(issue) for issue in issues]
                for rule, issues in self.by_rule.items()
            },
            "by_field": {
                field: [self._issue_to_dict(issue) for issue in issues]
                for field, issues in self.by_field.items()
            },
        }

    def to_dataframe(self) -> Any:
        try:
            pandas_module = importlib.import_module("pandas")
        except Exception as exc:  # pragma: no cover - import environment dependent
            raise RuntimeError(
                "pandas is not installed. Install extras with: pip install finschema[pandas]"
            ) from exc

        rows: list[dict[str, Any]] = []
        for issue in self._issues:
            row = self._issue_to_dict(issue)
            rows.append(row)
        return pandas_module.DataFrame(rows)

    @staticmethod
    def _issue_to_dict(issue: ValidationIssue) -> dict[str, Any]:
        return {
            "rule": issue.rule,
            "severity": issue.severity.value,
            "message": issue.message,
            "field": issue.field,
            "record_index": issue.record_index,
            "context": dict(issue.context),
        }
