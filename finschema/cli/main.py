from __future__ import annotations

import csv
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import typer

from finschema.errors import ValidationError
from finschema.quality import ValidationEngine
from finschema.types import BIC, CUSIP, IBAN, ISIN, LEI, SEDOL, BusinessDate, CurrencyCode

app = typer.Typer(help="finschema CLI")

_CHECKERS: dict[str, Callable[[str], object]] = {
    "isin": ISIN,
    "cusip": CUSIP,
    "sedol": SEDOL,
    "lei": LEI,
    "iban": IBAN,
    "bic": BIC,
    "currency": CurrencyCode,
    "business-date": BusinessDate,
}

_SCHEMAS: dict[str, str] = {
    "trade": "Trade",
    "position": "Position",
    "portfolio": "Portfolio",
}


class _CliUsageError(Exception):
    pass


class _CliRuntimeError(Exception):
    pass


def _resolve_schema_name(raw: str) -> str:
    key = raw.strip().lower()
    value = _SCHEMAS.get(key)
    if value is None:
        allowed = ", ".join(sorted(_SCHEMAS.values()))
        raise _CliUsageError(f"Unsupported schema '{raw}'. Use one of: {allowed}")
    return value


def _detect_format(path: Path, input_format: str) -> str:
    normalized = input_format.strip().lower()
    if normalized != "auto":
        if normalized not in {"csv", "parquet", "jsonl"}:
            raise _CliUsageError("Unsupported --format. Use one of: auto, csv, parquet, jsonl")
        return normalized

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".jsonl":
        return "jsonl"
    raise _CliUsageError(
        f"Could not detect format for {path}. Use --format with csv, parquet, or jsonl."
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise _CliRuntimeError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise _CliRuntimeError(f"Line {line_number} must be a JSON object")
            records.append(item)
    return records


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # type: ignore[import-untyped]

        frame = pd.read_parquet(path)
        return cast(list[dict[str, Any]], frame.to_dict(orient="records"))
    except Exception:
        pass

    try:
        import polars as pl

        frame = pl.read_parquet(path)
        return frame.to_dicts()
    except Exception as exc:
        raise _CliRuntimeError(
            "Parquet reading requires pandas or polars. Install extras with: "
            "pip install finschema[pandas] or pip install finschema[polars]"
        ) from exc


def _read_records(path: Path, input_format: str) -> list[dict[str, Any]]:
    resolved = _detect_format(path, input_format)
    if resolved == "csv":
        return _read_csv(path)
    if resolved == "jsonl":
        return _read_jsonl(path)
    if resolved == "parquet":
        return _read_parquet(path)
    raise _CliUsageError("Unsupported format")


@app.callback()
def main_callback() -> None:
    """finschema CLI."""


@app.command("check")
def check(identifier_type: str, value: str) -> None:
    """Validate a single value by finschema type."""
    checker = _CHECKERS.get(identifier_type.lower().strip())
    if checker is None:
        typer.echo("Unsupported type. Use one of: " + ", ".join(sorted(_CHECKERS.keys())))
        raise typer.Exit(code=2)

    try:
        validated = checker(value)
    except ValidationError as exc:
        typer.echo(f"✗ {value}")
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    typer.echo(f"✓ {validated}")


@app.command("validate")
def validate(
    path: str,
    schema: str = typer.Option(..., "--schema"),
    input_format: str = typer.Option("auto", "--format"),
    output: str | None = typer.Option(None, "--output"),
    output_json: str | None = typer.Option(None, "--output-json"),
    verbose: bool = typer.Option(False, "--verbose"),
    min_score: float | None = typer.Option(None, "--min-score"),
) -> None:
    """Validate records from file input against a schema."""
    try:
        schema_name = _resolve_schema_name(schema)
        file_path = Path(path)
        if not file_path.exists() or not file_path.is_file():
            raise _CliRuntimeError(f"Input file not found: {file_path}")

        records = _read_records(file_path, input_format)
        engine = ValidationEngine()
        overrides: dict[str, Any] | None = None
        if min_score is not None:
            overrides = {"min_score": min_score}
        report = engine.validate(records, schema=schema_name, overrides=overrides)

        stats = report.stats
        status = "PASS" if report.passed else "FAIL"
        typer.echo(f"finschema validate {file_path}")
        typer.echo(
            f"Schema: {schema_name} | Records: {stats['total_records']} | Score: {report.score:.4f} "
            f"| {status}"
        )
        typer.echo(
            f"Errors: {len(report.errors)} | Warnings: {len(report.warnings)} | "
            f"Info: {len(report.info)}"
        )

        if verbose:
            issues = report.errors + report.warnings + report.info
            for issue in issues[:20]:
                location = issue.field if issue.field is not None else "__root__"
                index = issue.record_index if issue.record_index is not None else "-"
                typer.echo(
                    f"[{issue.severity.value}] row={index} field={location} "
                    f"rule={issue.rule} msg={issue.message}"
                )
            if len(issues) > 20:
                typer.echo(f"... truncated {len(issues) - 20} additional issues")

        if output is not None:
            report.to_html(output)
            typer.echo(f"Saved HTML report to: {output}")
        if output_json is not None:
            report.to_json(output_json)
            typer.echo(f"Saved JSON report to: {output_json}")

        raise typer.Exit(code=0 if report.passed else 1)

    except _CliUsageError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    except _CliRuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=3) from exc


def main() -> None:
    app()


if __name__ == "__main__":
    main()
