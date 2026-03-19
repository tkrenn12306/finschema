"""Pandas DataFrame/Series integration."""

from __future__ import annotations

from collections.abc import Callable
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


def _resolve_schema_for_engine(schema: Any) -> type[BaseModel] | str | None:
    if isinstance(schema, str):
        return schema
    if isinstance(schema, type) and issubclass(schema, BaseModel):
        return schema
    return None


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


@pd.api.extensions.register_series_accessor("finschema")
class FinschemaSeriesAccessor:
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

    def is_valid(
        self,
        schema: Any,
        *,
        engine: ValidationEngine | None = None,
        context: dict[str, Any] | None = None,
        overrides: dict[str, Any] | None = None,
    ) -> pd.Series[bool]:
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


def register_pandas_accessors() -> None:
    """Kept for explicit API completeness. Accessors are registered on import."""


__all__ = ["register_pandas_accessors"]
