"""Pandas DataFrame/Series integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from finschema.errors import ValidationError
from finschema.quality import Severity, ValidationEngine, ValidationIssue
from finschema.quality.report import QualityReport

try:
    import pandas as pd  # type: ignore[import-untyped]
except Exception as exc:  # pragma: no cover - depends on optional dependency
    raise RuntimeError(
        "pandas is not installed. Install extras with: pip install finschema[pandas]"
    ) from exc

_CODE_COLUMN_HINTS = {
    "isin",
    "currency",
    "bic",
    "lei",
    "cusip",
    "sedol",
    "figi",
    "valor",
    "wkn",
    "ric",
    "ticker",
    "country",
    "mic",
    "side",
    "asset_class",
}


@dataclass(frozen=True, slots=True)
class RowValidationResult:
    """Per-row validation result for series-level validation."""

    index: Any
    value: Any
    is_valid: bool
    errors: tuple[str, ...] = ()


def _resolve_schema_for_engine(schema: Any) -> type[BaseModel] | str | None:
    if isinstance(schema, str):
        return schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema
    return None


def _looks_like_code_column(column: str) -> bool:
    normalized = column.strip().lower()
    return any(hint in normalized for hint in _CODE_COLUMN_HINTS)


def _looks_like_date_column(column: str) -> bool:
    normalized = column.strip().lower()
    return normalized.endswith(("_date", "date"))


def _count_changes(before: pd.Series[Any], after: pd.Series[Any]) -> int:
    before_norm = before.astype("string").fillna("<NA>")
    after_norm = after.astype("string").fillna("<NA>")
    return int((before_norm != after_norm).sum())


def _extend_report(report: QualityReport, additional: list[ValidationIssue]) -> QualityReport:
    if not additional:
        return report

    return QualityReport(
        issues=report.issues + additional,
        total_records=int(report.stats.get("total_records", 0)),
        min_score=float(getattr(report, "_min_score", 0.95)),
        total_checks=int(
            getattr(report, "_total_checks", max(int(report.stats.get("total_records", 0)), 1))
        ),
        fail_on_severity=getattr(report, "_fail_on_severity", Severity.ERROR),
    )


def _validation_mask_from_report(report: QualityReport, index: pd.Index[Any]) -> pd.Series[bool]:
    mask = pd.Series(True, index=index, dtype=bool)
    invalid_positions = {
        issue.record_index for issue in report.errors if issue.record_index is not None
    }
    has_global_error = any(issue.record_index is None for issue in report.errors)

    if has_global_error:
        mask[:] = False
        return mask

    for pos in invalid_positions:
        if 0 <= pos < len(mask):
            mask.iloc[pos] = False

    return mask


def _coerce_dataframe_values(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[ValidationIssue]]:
    coerced = frame.copy(deep=True)
    issues: list[ValidationIssue] = []

    for column in coerced.columns:
        series_before = coerced[column]
        series_after = series_before

        if pd.api.types.is_string_dtype(series_before) or series_before.dtype == object:
            series_after = series_after.map(
                lambda value: value.strip() if isinstance(value, str) else value
            )

            if _looks_like_code_column(str(column)):
                series_after = series_after.map(
                    lambda value: value.upper() if isinstance(value, str) else value
                )

            if _looks_like_date_column(str(column)):
                parsed = pd.to_datetime(series_after, errors="coerce")
                formatted = parsed.dt.strftime("%Y-%m-%d")
                series_after = series_after.copy()
                valid_date_mask = parsed.notna()
                series_after.loc[valid_date_mask] = formatted.loc[valid_date_mask]

        if not series_after.equals(series_before):
            coerced[column] = series_after
            change_count = _count_changes(series_before, series_after)
            issues.append(
                ValidationIssue(
                    rule="coerce_changes",
                    severity=Severity.INFO,
                    message=f"Coerced {change_count} value(s) in column {column}",
                    field=str(column),
                    context={"changed": change_count},
                )
            )

    return coerced, issues


def _validate_scalar_series(
    series: pd.Series[Any], validator: Callable[[Any], Any]
) -> QualityReport:
    issues: list[ValidationIssue] = []
    for index, value in series.items():
        try:
            validator(value)
        except ValidationError as exc:
            issues.append(
                ValidationIssue(
                    rule="series_validation",
                    severity=Severity.ERROR,
                    message=str(exc),
                    field=str(series.name) if series.name is not None else "__root__",
                    record_index=int(index) if isinstance(index, int) else None,
                    context={"value": str(value)},
                )
            )
    return QualityReport(issues=issues, total_records=len(series))


@pd.api.extensions.register_dataframe_accessor("finschema")
class FinschemaDataFrameAccessor:
    """Namespace accessor for DataFrame-level finschema operations."""

    def __init__(self, pandas_obj: pd.DataFrame) -> None:
        self._obj = pandas_obj

    def validate(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> QualityReport:
        """Validate all rows against a finschema schema and return a quality report."""
        runtime_engine = engine or ValidationEngine()
        records = self._obj.to_dict(orient="records")
        return runtime_engine.validate(records, schema=schema, context=context, overrides=overrides)

    def is_valid(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> pd.Series[bool]:
        """Return a boolean mask indicating valid rows for the provided schema."""
        runtime_engine = engine or ValidationEngine()
        records = self._obj.to_dict(orient="records")
        flags = [
            len(
                runtime_engine.validate(
                    record,
                    schema=schema,
                    context=context,
                    overrides=overrides,
                ).errors
            )
            == 0
            for record in records
        ]
        return pd.Series(flags, index=self._obj.index, dtype=bool)

    def clean(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[pd.DataFrame, QualityReport]:
        """Return a DataFrame containing only valid rows and a report of removals/issues."""
        report = self.validate(schema, engine=engine, context=context, overrides=overrides)
        valid_mask = _validation_mask_from_report(report, self._obj.index)
        cleaned = self._obj.loc[valid_mask].copy()
        removed = int((~valid_mask).sum())

        extra_issues: list[ValidationIssue] = []
        if removed > 0:
            extra_issues.append(
                ValidationIssue(
                    rule="clean_removed_rows",
                    severity=Severity.INFO,
                    message=f"Removed {removed} invalid row(s)",
                    field="__root__",
                    context={"removed_rows": removed},
                )
            )

        return cleaned, _extend_report(report, extra_issues)

    def coerce(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[pd.DataFrame, QualityReport]:
        """Apply deterministic coercions, then validate and return coerced data + report."""
        coerced, coercion_issues = _coerce_dataframe_values(self._obj)
        runtime_engine = engine or ValidationEngine()
        report = runtime_engine.validate(
            coerced.to_dict(orient="records"),
            schema=schema,
            context=context,
            overrides=overrides,
        )
        return coerced, _extend_report(report, coercion_issues)


@pd.api.extensions.register_series_accessor("finschema")
class FinschemaSeriesAccessor:
    """Namespace accessor for Series-level finschema operations."""

    def __init__(self, pandas_obj: pd.Series[Any]) -> None:
        self._obj = pandas_obj

    def validate(
        self,
        schema: Any,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> QualityReport:
        """Validate each element and return a QualityReport (backward compatible API)."""
        runtime_engine = engine or ValidationEngine()
        engine_schema = _resolve_schema_for_engine(schema)
        if engine_schema is not None:
            records = self._obj.tolist()
            return runtime_engine.validate(
                records,
                schema=engine_schema,
                context=context,
                overrides=overrides,
            )
        if callable(schema):
            return _validate_scalar_series(self._obj, schema)
        raise TypeError("Series schema must be a schema name/type or a callable validator")

    def validate_rows(
        self,
        schema: Any,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> list[RowValidationResult]:
        """Return per-row validation results for this series."""
        runtime_engine = engine or ValidationEngine()
        engine_schema = _resolve_schema_for_engine(schema)

        results: list[RowValidationResult] = []
        if engine_schema is not None:
            for index, value in self._obj.items():
                report = runtime_engine.validate(
                    value,
                    schema=engine_schema,
                    context=context,
                    overrides=overrides,
                )
                errors = tuple(issue.message for issue in report.errors)
                results.append(
                    RowValidationResult(
                        index=index,
                        value=value,
                        is_valid=len(errors) == 0,
                        errors=errors,
                    )
                )
            return results

        if callable(schema):
            for index, value in self._obj.items():
                try:
                    schema(value)
                except ValidationError as exc:
                    results.append(
                        RowValidationResult(
                            index=index,
                            value=value,
                            is_valid=False,
                            errors=(exc.message,),
                        )
                    )
                else:
                    results.append(
                        RowValidationResult(index=index, value=value, is_valid=True, errors=())
                    )
            return results

        raise TypeError("Series schema must be a schema name/type or a callable validator")

    def is_valid(
        self,
        schema: Any,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> pd.Series[bool]:
        """Return a boolean mask for per-element validity."""
        runtime_engine = engine or ValidationEngine()
        engine_schema = _resolve_schema_for_engine(schema)
        if engine_schema is not None:
            flags: list[bool] = []
            for value in self._obj.tolist():
                report = runtime_engine.validate(
                    value,
                    schema=engine_schema,
                    context=context,
                    overrides=overrides,
                )
                flags.append(len(report.errors) == 0)
            return pd.Series(flags, index=self._obj.index, dtype=bool)

        if callable(schema):
            flags = []
            for value in self._obj.tolist():
                try:
                    schema(value)
                except ValidationError:
                    flags.append(False)
                else:
                    flags.append(True)
            return pd.Series(flags, index=self._obj.index, dtype=bool)

        raise TypeError("Series schema must be a schema name/type or a callable validator")


def read_csv(
    path: str | Path,
    *,
    schema: type[BaseModel] | str,
    engine: ValidationEngine | None = None,
    context: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
    **kwargs: Any,
) -> tuple[pd.DataFrame, QualityReport]:
    """Read a CSV file and immediately validate it against a finschema schema."""
    frame = pd.read_csv(path, **kwargs)
    report = frame.finschema.validate(schema, engine=engine, context=context, overrides=overrides)
    return frame, report


def register_pandas_accessors() -> None:
    """Kept for explicit API completeness. Accessors are registered on import."""


__all__ = ["RowValidationResult", "read_csv", "register_pandas_accessors"]
