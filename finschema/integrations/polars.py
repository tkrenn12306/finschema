"""Polars DataFrame/Series integration."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from finschema.errors import ValidationError
from finschema.quality import Severity, ValidationEngine, ValidationIssue
from finschema.quality.report import QualityReport

try:
    import polars as pl
except Exception as exc:  # pragma: no cover - depends on optional dependency
    raise RuntimeError(
        "polars is not installed. Install extras with: pip install finschema[polars]"
    ) from exc


def _resolve_schema_for_engine(schema: Any) -> type[BaseModel] | str | None:
    if isinstance(schema, str):
        return schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema
    return None


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


@pl.api.register_series_namespace("finschema")
class FinschemaPolarsSeriesAccessor:
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

    def is_valid(
        self,
        schema: Any,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> pl.Series:
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


def register_polars_namespace() -> None:
    """Kept for explicit API completeness. Accessors are registered on import."""


__all__ = ["register_polars_namespace"]
