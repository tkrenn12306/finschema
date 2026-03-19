from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, cast

from finschema.errors import ValidationError
from finschema.quality import QualityReport, ValidationEngine
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
        if normalized not in {"csv", "parquet", "json", "jsonl"}:
            raise CliUsageError("Unsupported --format. Use one of: auto, csv, parquet, json, jsonl")
        return normalized

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix == ".parquet":
        return "parquet"
    if suffix == ".jsonl":
        return "jsonl"
    if suffix == ".json":
        return "json"
    raise CliUsageError(
        f"Could not detect format for {path}. Use --format with csv, parquet, json, or jsonl."
    )


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CliRuntimeError(f"Invalid JSON in {path}: {exc}") from exc

    if isinstance(payload, dict):
        return [payload]

    if isinstance(payload, list):
        records: list[dict[str, Any]] = []
        for index, item in enumerate(payload):
            if not isinstance(item, dict):
                raise CliRuntimeError(f"JSON array item at index {index} must be an object")
            records.append(item)
        return records

    raise CliRuntimeError("JSON payload must be an object or list of objects")


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
        records: list[dict[str, Any]] = frame.to_dicts()
        return records
    except Exception as exc:
        raise CliRuntimeError(
            "Parquet reading requires pandas or polars. Install extras with: "
            "pip install finschema[pandas] or pip install finschema[polars]"
        ) from exc


def _read_records(path: Path, input_format: str) -> list[dict[str, Any]]:
    resolved = _detect_format(path, input_format)
    if resolved == "csv":
        return _read_csv(path)
    if resolved == "json":
        return _read_json(path)
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


def _build_engine(config_path: str | None) -> ValidationEngine:
    try:
        return ValidationEngine(config=config_path if config_path else None)
    except Exception as exc:  # pragma: no cover - defensive, validated in tests
        raise CliRuntimeError(f"Unable to load validation config: {exc}") from exc


def _run_engine_validate(
    records: list[dict[str, Any]],
    *,
    schema_name: str,
    engine: ValidationEngine,
    min_score: float | None,
) -> QualityReport:
    overrides: dict[str, Any] | None = None
    if min_score is not None:
        overrides = {"min_score": min_score}

    try:
        return engine.validate(records, schema=schema_name, overrides=overrides)
    except ValidationError as exc:
        raise CliRuntimeError(f"Validation failed in strict mode: {exc.message}") from exc


def _print_report(
    report: QualityReport, *, file_path: Path, schema_name: str, verbose: bool
) -> None:
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

    if verbose:
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


def _run_validate_once(args: argparse.Namespace) -> int:
    schema_name = _resolve_schema_name(args.schema)
    file_path = Path(args.path)
    if not file_path.exists() or not file_path.is_file():
        raise CliRuntimeError(f"Input file not found: {file_path}")

    records = _read_records(file_path, args.input_format)
    engine = _build_engine(args.config)
    report = _run_engine_validate(
        records,
        schema_name=schema_name,
        engine=engine,
        min_score=args.min_score,
    )

    _print_report(report, file_path=file_path, schema_name=schema_name, verbose=args.verbose)

    if args.output is not None:
        report.to_html(args.output, records=records)
        print(f"Saved HTML report to: {args.output}")
    if args.output_json is not None:
        report.to_json(args.output_json)
        print(f"Saved JSON report to: {args.output_json}")

    return 0 if report.passed else 1


def _run_validate(args: argparse.Namespace) -> int:
    if not args.watch:
        return _run_validate_once(args)

    file_path = Path(args.path)
    if not file_path.exists() or not file_path.is_file():
        raise CliRuntimeError(f"Input file not found: {file_path}")

    last_mtime_ns: int | None = None
    last_code = 0
    remaining_cycles = args.watch_cycles if args.watch_cycles > 0 else None

    try:
        while True:
            try:
                current_mtime_ns = file_path.stat().st_mtime_ns
            except OSError as exc:
                raise CliRuntimeError(f"Unable to stat watched file: {exc}") from exc

            if last_mtime_ns is None or current_mtime_ns != last_mtime_ns:
                if last_mtime_ns is None:
                    print("Watch mode started. Press Ctrl+C to stop.")
                else:
                    print(f"Change detected in {file_path}, re-validating...")
                last_code = _run_validate_once(args)
                last_mtime_ns = current_mtime_ns

                if remaining_cycles is not None:
                    remaining_cycles -= 1
                    if remaining_cycles <= 0:
                        return last_code

            time.sleep(max(float(args.watch_interval), 0.1))
    except KeyboardInterrupt:
        return last_code


def _run_diff(args: argparse.Namespace) -> int:
    schema_name = _resolve_schema_name(args.schema)
    path_a = Path(args.file_a)
    path_b = Path(args.file_b)

    if not path_a.exists() or not path_a.is_file():
        raise CliRuntimeError(f"Input file not found: {path_a}")
    if not path_b.exists() or not path_b.is_file():
        raise CliRuntimeError(f"Input file not found: {path_b}")

    records_a = _read_records(path_a, args.input_format)
    records_b = _read_records(path_b, args.input_format)

    engine = _build_engine(args.config)
    report_a = _run_engine_validate(
        records_a,
        schema_name=schema_name,
        engine=engine,
        min_score=args.min_score,
    )
    report_b = _run_engine_validate(
        records_b,
        schema_name=schema_name,
        engine=engine,
        min_score=args.min_score,
    )

    delta_score = report_b.score - report_a.score
    new_errors = max(0, len(report_b.errors) - len(report_a.errors))
    resolved_errors = max(0, len(report_a.errors) - len(report_b.errors))

    print(f"finschema diff {path_a} -> {path_b}")
    print(f"Schema: {schema_name}")
    print(
        f"Score A: {report_a.score:.4f} | Score B: {report_b.score:.4f} | Delta: {delta_score:+.4f}"
    )
    print(
        f"Errors A: {len(report_a.errors)} | Errors B: {len(report_b.errors)} | "
        f"New: {new_errors} | Resolved: {resolved_errors}"
    )

    if args.output_json is not None:
        payload = {
            "schema": schema_name,
            "file_a": str(path_a),
            "file_b": str(path_b),
            "score_a": report_a.score,
            "score_b": report_b.score,
            "delta_score": delta_score,
            "errors_a": len(report_a.errors),
            "errors_b": len(report_b.errors),
            "new_errors": new_errors,
            "resolved_errors": resolved_errors,
        }
        Path(args.output_json).write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(f"Saved diff JSON report to: {args.output_json}")

    return 0 if report_b.passed else 1


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
    validate.add_argument("path", help="CSV, JSON, JSONL, or Parquet file")
    validate.add_argument("--schema", required=True, help="Trade|Position|Portfolio")
    validate.add_argument(
        "--format", dest="input_format", default="auto", help="auto|csv|json|jsonl|parquet"
    )
    validate.add_argument("--output", default=None, help="HTML report output path")
    validate.add_argument("--output-json", default=None, help="JSON report output path")
    validate.add_argument("--verbose", action="store_true")
    validate.add_argument("--min-score", type=float, default=None)
    validate.add_argument("--config", default=None, help="Validation config path (.yaml/.toml)")
    validate.add_argument("--watch", action="store_true", help="Re-validate when file changes")
    validate.add_argument(
        "--watch-interval",
        type=float,
        default=1.0,
        help="Polling interval in seconds for --watch mode",
    )
    validate.add_argument("--watch-cycles", type=int, default=0, help=argparse.SUPPRESS)

    diff = sub.add_parser("diff", help="Compare quality between two files")
    diff.add_argument("file_a", help="Baseline file")
    diff.add_argument("file_b", help="Comparison file")
    diff.add_argument("--schema", required=True, help="Trade|Position|Portfolio")
    diff.add_argument(
        "--format", dest="input_format", default="auto", help="auto|csv|json|jsonl|parquet"
    )
    diff.add_argument("--min-score", type=float, default=None)
    diff.add_argument("--config", default=None, help="Validation config path (.yaml/.toml)")
    diff.add_argument("--output-json", default=None, help="Write machine-readable diff report")

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
        if args.command == "diff":
            return _run_diff(args)
        raise CliUsageError("Unsupported command")
    except CliUsageError as exc:
        print(str(exc))
        return 2
    except CliRuntimeError as exc:
        print(str(exc))
        return 3


if __name__ == "__main__":
    sys.exit(main())
