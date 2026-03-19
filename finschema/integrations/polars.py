"""Polars DataFrame/Series/LazyFrame integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from finschema.errors import ValidationError
from finschema.quality import Severity, ValidationEngine, ValidationIssue
from finschema.quality.report import QualityReport
from finschema.types import BIC, ISIN, CurrencyCode

try:
    import polars as pl
except Exception as exc:  # pragma: no cover - depends on optional dependency
    raise RuntimeError(
        "polars is not installed. Install extras with: pip install finschema[polars]"
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

    index: int
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


def _extend_report(report: QualityReport, additional: list[ValidationIssue]) -> QualityReport:
    if not additional:
        return report

    return QualityReport(
        issues=report.issues + additional,
        total_records=int(report.stats.get("total_records", 0)),
        min_score=float(getattr(report, "_min_score", 0.95)),
        total_checks=int(
            getattr(
                report,
                "_total_checks",
                max(int(report.stats.get("total_records", 0)), 1),
            )
        ),
        fail_on_severity=getattr(report, "_fail_on_severity", Severity.ERROR),
    )


def _validation_mask_from_report(report: QualityReport, size: int) -> list[bool]:
    mask = [True] * size
    invalid_positions = {
        issue.record_index for issue in report.errors if issue.record_index is not None
    }
    has_global_error = any(issue.record_index is None for issue in report.errors)

    if has_global_error:
        return [False] * size

    for pos in invalid_positions:
        if 0 <= pos < size:
            mask[pos] = False

    return mask


def _coerce_dataframe_values(frame: pl.DataFrame) -> tuple[pl.DataFrame, list[ValidationIssue]]:
    expressions: list[pl.Expr] = []
    candidate_columns: list[str] = []

    for column in frame.columns:
        if frame[column].dtype != pl.Utf8:
            continue

        candidate_columns.append(column)
        expr = pl.col(column).str.strip_chars()

        if _looks_like_code_column(column):
            expr = expr.str.to_uppercase()

        if _looks_like_date_column(column):
            parsed_dt = expr.str.strptime(pl.Datetime, strict=False)
            parsed_date = expr.str.strptime(pl.Date, strict=False)
            expr = (
                pl.when(parsed_dt.is_not_null())
                .then(parsed_dt.dt.strftime("%Y-%m-%d"))
                .when(parsed_date.is_not_null())
                .then(parsed_date.dt.strftime("%Y-%m-%d"))
                .otherwise(expr)
            )

        expressions.append(expr.alias(column))

    if not expressions:
        return frame, []

    coerced = frame.with_columns(expressions)
    issues: list[ValidationIssue] = []

    for column in candidate_columns:
        before_values = frame[column].to_list()
        after_values = coerced[column].to_list()
        changes = sum(
            1 for before, after in zip(before_values, after_values, strict=True) if before != after
        )
        if changes > 0:
            issues.append(
                ValidationIssue(
                    rule="coerce_changes",
                    severity=Severity.INFO,
                    message=f"Coerced {changes} value(s) in column {column}",
                    field=column,
                    context={"changed": changes},
                )
            )

    return coerced, issues


def _validate_scalar_series(series: pl.Series, validator: Callable[[Any], Any]) -> QualityReport:
    issues: list[ValidationIssue] = []
    for index, value in enumerate(series.to_list()):
        try:
            validator(value)
        except ValidationError as exc:
            issues.append(
                ValidationIssue(
                    rule="series_validation",
                    severity=Severity.ERROR,
                    message=str(exc),
                    field=series.name,
                    record_index=index,
                    context={"value": str(value)},
                )
            )
    return QualityReport(issues=issues, total_records=series.len())


@pl.api.register_dataframe_namespace("finschema")
class FinschemaPolarsDataFrameAccessor:
    """Namespace accessor for Polars DataFrame-level operations."""

    def __init__(self, polars_obj: pl.DataFrame) -> None:
        self._obj = polars_obj

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
        records = self._obj.to_dicts()
        return runtime_engine.validate(records, schema=schema, context=context, overrides=overrides)

    def is_valid(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> pl.Series:
        """Return a boolean mask indicating valid rows for the provided schema."""
        runtime_engine = engine or ValidationEngine()
        records = self._obj.to_dicts()
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
        return pl.Series(name="finschema_is_valid", values=flags)

    def clean(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[pl.DataFrame, QualityReport]:
        """Return only valid rows and a report describing removed rows/issues."""
        report = self.validate(schema, engine=engine, context=context, overrides=overrides)
        mask = _validation_mask_from_report(report, self._obj.height)
        cleaned = self._obj.filter(pl.Series(name="finschema_is_valid", values=mask))
        removed = len(mask) - sum(mask)

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
    ) -> tuple[pl.DataFrame, QualityReport]:
        """Apply deterministic coercions, then validate and return coerced data + report."""
        coerced, coercion_issues = _coerce_dataframe_values(self._obj)
        runtime_engine = engine or ValidationEngine()
        report = runtime_engine.validate(
            coerced.to_dicts(),
            schema=schema,
            context=context,
            overrides=overrides,
        )
        return coerced, _extend_report(report, coercion_issues)


@pl.api.register_series_namespace("finschema")
class FinschemaPolarsSeriesAccessor:
    """Namespace accessor for Polars Series-level operations."""

    def __init__(self, polars_obj: pl.Series) -> None:
        self._obj = polars_obj

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
            return runtime_engine.validate(
                self._obj.to_list(),
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
            for index, value in enumerate(self._obj.to_list()):
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
            for index, value in enumerate(self._obj.to_list()):
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
    ) -> pl.Series:
        """Return a boolean mask for per-element validity."""
        runtime_engine = engine or ValidationEngine()
        engine_schema = _resolve_schema_for_engine(schema)
        if engine_schema is not None:
            flags: list[bool] = []
            for value in self._obj.to_list():
                report = runtime_engine.validate(
                    value,
                    schema=engine_schema,
                    context=context,
                    overrides=overrides,
                )
                flags.append(len(report.errors) == 0)
            return pl.Series(name="finschema_is_valid", values=flags)

        if callable(schema):
            callable_flags: list[bool] = []
            for value in self._obj.to_list():
                try:
                    schema(value)
                except ValidationError:
                    callable_flags.append(False)
                else:
                    callable_flags.append(True)
            return pl.Series(name="finschema_is_valid", values=callable_flags)

        raise TypeError("Series schema must be a schema name/type or a callable validator")


@pl.api.register_lazyframe_namespace("finschema")
class FinschemaPolarsLazyFrameAccessor:
    """Namespace accessor for Polars LazyFrame validation operations."""

    def __init__(self, polars_obj: pl.LazyFrame) -> None:
        self._obj = polars_obj

    def validate(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> QualityReport:
        """Collect and validate a lazy frame."""
        accessor = FinschemaPolarsDataFrameAccessor(self._obj.collect())
        return accessor.validate(
            schema,
            engine=engine,
            context=context,
            overrides=overrides,
        )

    def is_valid(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> pl.Series:
        """Collect and return a boolean validity mask for each row."""
        accessor = FinschemaPolarsDataFrameAccessor(self._obj.collect())
        return accessor.is_valid(
            schema,
            engine=engine,
            context=context,
            overrides=overrides,
        )

    def clean(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[pl.LazyFrame, QualityReport]:
        """Collect, clean invalid rows, and return LazyFrame + report."""
        accessor = FinschemaPolarsDataFrameAccessor(self._obj.collect())
        cleaned, report = accessor.clean(
            schema,
            engine=engine,
            context=context,
            overrides=overrides,
        )
        return cleaned.lazy(), report

    def coerce(
        self,
        schema: type[BaseModel] | str,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> tuple[pl.LazyFrame, QualityReport]:
        """Collect, coerce values, and return LazyFrame + report."""
        accessor = FinschemaPolarsDataFrameAccessor(self._obj.collect())
        coerced, report = accessor.coerce(
            schema,
            engine=engine,
            context=context,
            overrides=overrides,
        )
        return coerced.lazy(), report


class _ExprValidators:
    """Expression-based validators for Polars workflows."""

    @staticmethod
    def _to_expr(column: str | pl.Expr) -> pl.Expr:
        return pl.col(column) if isinstance(column, str) else column

    @staticmethod
    def _validator_expr(column: str | pl.Expr, validator: Callable[[Any], Any]) -> pl.Expr:
        base = _ExprValidators._to_expr(column)

        def _validate(value: Any) -> bool:
            try:
                validator(value)
            except Exception:
                return False
            return True

        return base.map_elements(_validate, return_dtype=pl.Boolean)

    def is_valid_isin(self, column: str | pl.Expr) -> pl.Expr:
        """Return a Polars expression that validates ISIN values."""
        return self._validator_expr(column, ISIN)

    def is_valid_currency(self, column: str | pl.Expr) -> pl.Expr:
        """Return a Polars expression that validates CurrencyCode values."""
        return self._validator_expr(column, CurrencyCode)

    def is_valid_bic(self, column: str | pl.Expr) -> pl.Expr:
        """Return a Polars expression that validates BIC values."""
        return self._validator_expr(column, BIC)


expr = _ExprValidators()


def register_polars_namespace() -> None:
    """Kept for explicit API completeness. Accessors are registered on import."""


__all__ = ["RowValidationResult", "expr", "register_polars_namespace"]
