from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, cast

from finschema.errors import ValidationError
from finschema.quality import ValidationEngine
from finschema.reference import get_country_info
from finschema.types import (
    BIC,
    CUSIP,
    IBAN,
    ISIN,
    LEI,
    SEDOL,
    BusinessDate,
    CurrencyCode,
)

_CHECKERS: dict[str, Any] = {
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

_ANSI = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "reset": "\033[0m",
}


class CliUsageError(Exception):
    pass


class CliRuntimeError(Exception):
    pass


def _color(text: str, color: str, *, enabled: bool) -> str:
    if not enabled:
        return text
    return f"{_ANSI[color]}{text}{_ANSI['reset']}"


def _resolve_schema_name(raw: str) -> str:
    key = raw.strip().lower()
    value = _SCHEMAS.get(key)
    if value is None:
        allowed = ", ".join(sorted(_SCHEMAS.values()))
        raise CliUsageError(f"Unsupported schema '{raw}'. Use one of: {allowed}")
    return value


def _detect_format(path: Path, input_format: str) -> str:
    normalized = input_format.strip().lower()
    if normalized != "auto":
        if normalized not in {"csv", "parquet", "jsonl"}:
            raise CliUsageError("Unsupported --format. Use one of: auto, csv, parquet, jsonl")
        return normalized

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".jsonl":
        return "jsonl"
    raise CliUsageError(
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
                raise CliRuntimeError(f"Invalid JSON on line {line_number}: {exc}") from exc
            if not isinstance(item, dict):
                raise CliRuntimeError(f"Line {line_number} must be a JSON object")
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
        raise CliRuntimeError(
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
    raise CliUsageError("Unsupported format")


def _identifier_detail(identifier_type: str, validated: Any) -> str:
    value = str(validated)
    if identifier_type == "isin":
        country = get_country_info(value[:2]).name
        return f"Valid ISIN ({country}, check digit: {value[-1]})"
    if identifier_type == "cusip":
        return f"Valid CUSIP (check digit: {value[-1]})"
    if identifier_type == "sedol":
        return f"Valid SEDOL (check digit: {value[-1]})"
    if identifier_type == "lei":
        return f"Valid LEI (check digits: {value[-2:]})"
    if identifier_type == "iban":
        return f"Valid IBAN (country: {value[:2]}, check digits: {value[2:4]})"
    if identifier_type == "bic":
        return f"Valid BIC (country: {value[4:6]})"
    if identifier_type == "currency":
        return f"Valid CurrencyCode (decimals: {validated.decimals})"
    if identifier_type == "business-date":
        return "Valid BusinessDate"
    return "Valid"


def _run_check(args: argparse.Namespace) -> int:
    identifier_type = args.identifier_type.lower().strip()
    checker = _CHECKERS.get(identifier_type)
    color_enabled = not args.no_color
    if checker is None:
        raise CliUsageError("Unsupported type. Use one of: " + ", ".join(sorted(_CHECKERS.keys())))

    if args.batch is not None:
        path = Path(args.batch)
        if not path.exists() or not path.is_file():
            raise CliRuntimeError(f"Batch file not found: {path}")

        total = 0
        valid = 0
        invalid = 0
        failures: list[str] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            value = line.strip()
            if not value:
                continue
            total += 1
            try:
                checker(value)
            except ValidationError as exc:
                invalid += 1
                failures.append(f"{value}: {exc.message}")
            else:
                valid += 1

        status = "PASS" if invalid == 0 else "FAIL"
        color = "green" if invalid == 0 else "red"
        print(_color(f"{status} batch check ({identifier_type})", color, enabled=color_enabled))
        print(f"Total: {total} | Valid: {valid} | Invalid: {invalid}")
        if failures:
            print("Top issues:")
            for item in failures[:10]:
                print(f"  - {item}")
        return 0 if invalid == 0 else 1

    if not args.value:
        raise CliUsageError("check requires <value> or --batch <file>")
    value = args.value
    try:
        validated = checker(value)
    except ValidationError as exc:
        print(_color(f"✗ {value}", "red", enabled=color_enabled))
        print(str(exc))
        return 1

    detail = _identifier_detail(identifier_type, validated)
    print(_color(f"✓ {validated} — {detail}", "green", enabled=color_enabled))
    return 0


def _run_validate(args: argparse.Namespace) -> int:
    schema_name = _resolve_schema_name(args.schema)
    file_path = Path(args.path)
    if not file_path.exists() or not file_path.is_file():
        raise CliRuntimeError(f"Input file not found: {file_path}")

    records = _read_records(file_path, args.input_format)
    engine = ValidationEngine()
    overrides: dict[str, Any] | None = None
    if args.min_score is not None:
        overrides = {"min_score": args.min_score}
    report = engine.validate(records, schema=schema_name, overrides=overrides)

    stats = report.stats
    status = "PASS" if report.passed else "FAIL"
    print(f"finschema validate {file_path}")
    print(
        f"Schema: {schema_name} | Records: {stats['total_records']} | "
        f"Score: {report.score:.4f} | {status}"
    )
    print(
        f"Errors: {len(report.errors)} | Warnings: {len(report.warnings)} | Info: {len(report.info)}"
    )

    if args.verbose:
        issues = report.errors + report.warnings + report.info
        for issue in issues[:20]:
            location = issue.field if issue.field is not None else "__root__"
            index = issue.record_index if issue.record_index is not None else "-"
            print(
                f"[{issue.severity.value}] row={index} field={location} "
                f"rule={issue.rule} msg={issue.message}"
            )
        if len(issues) > 20:
            print(f"... truncated {len(issues) - 20} additional issues")

    if args.output is not None:
        report.to_html(args.output)
        print(f"Saved HTML report to: {args.output}")
    if args.output_json is not None:
        report.to_json(args.output_json)
        print(f"Saved JSON report to: {args.output_json}")

    return 0 if report.passed else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="finschema", description="finschema CLI")
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("check", help="Validate single values or a batch file")
    check.add_argument(
        "identifier_type", help="isin|cusip|sedol|lei|iban|bic|currency|business-date"
    )
    check.add_argument("value", nargs="?", default="", help="Value to validate")
    check.add_argument("--batch", dest="batch", default=None, help="Batch file, one value per line")
    check.add_argument("--no-color", action="store_true", help="Disable ANSI colors")

    validate = sub.add_parser("validate", help="Validate records from file input")
    validate.add_argument("path", help="CSV, JSONL, or Parquet file")
    validate.add_argument("--schema", required=True, help="Trade|Position|Portfolio")
    validate.add_argument(
        "--format", dest="input_format", default="auto", help="auto|csv|jsonl|parquet"
    )
    validate.add_argument("--output", default=None, help="HTML report output path")
    validate.add_argument("--output-json", default=None, help="JSON report output path")
    validate.add_argument("--verbose", action="store_true")
    validate.add_argument("--min-score", type=float, default=None)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 2
    try:
        if args.command == "check":
            return _run_check(args)
        if args.command == "validate":
            return _run_validate(args)
        raise CliUsageError("Unsupported command")
    except CliUsageError as exc:
        print(str(exc))
        return 2
    except CliRuntimeError as exc:
        print(str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main())
