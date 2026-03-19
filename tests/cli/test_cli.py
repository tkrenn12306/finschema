from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from finschema.cli.main import main


def _run_cli(args: list[str]) -> tuple[int, str]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(args)
    return code, buffer.getvalue()


def test_cli_check_valid_isin() -> None:
    code, out = _run_cli(["check", "isin", "US0378331005", "--no-color"])
    assert code == 0
    assert "Valid ISIN" in out


def test_cli_check_invalid_isin() -> None:
    code, out = _run_cli(["check", "isin", "US0378331009", "--no-color"])
    assert code == 1
    assert "Invalid ISIN check digit" in out


def test_cli_unsupported_type() -> None:
    code, out = _run_cli(["check", "foo", "bar"])
    assert code == 2
    assert "Unsupported type" in out


def test_cli_help() -> None:
    code, out = _run_cli([])
    assert code == 2
    assert "finschema CLI" in out


def _write_trade_csv(path: Path, *, invalid_isin: bool = False) -> None:
    isin = "US0378331009" if invalid_isin else "US0378331005"
    path.write_text(
        "trade_id,isin,side,quantity,price,currency,trade_date,settlement_date\n"
        f"T-1,{isin},BUY,100,178.52,USD,2026-03-19,2026-03-20\n",
        encoding="utf-8",
    )


def test_cli_validate_csv_pass(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    _write_trade_csv(input_file, invalid_isin=False)

    code, out = _run_cli(["validate", str(input_file), "--schema", "Trade"])
    assert code == 0
    assert "Schema: Trade" in out
    assert "PASS" in out


def test_cli_validate_csv_fail(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    _write_trade_csv(input_file, invalid_isin=True)

    code, out = _run_cli(["validate", str(input_file), "--schema", "Trade"])
    assert code == 1
    assert "FAIL" in out


def test_cli_validate_jsonl_pass(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.jsonl"
    record = {
        "trade_id": "T-1",
        "isin": "US0378331005",
        "side": "BUY",
        "quantity": 100,
        "price": 178.52,
        "currency": "USD",
        "trade_date": "2026-03-19",
        "settlement_date": "2026-03-20",
    }
    input_file.write_text(json.dumps(record) + "\n", encoding="utf-8")

    code, _out = _run_cli(["validate", str(input_file), "--schema", "Trade"])
    assert code == 0


def test_cli_validate_usage_error(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    _write_trade_csv(input_file)

    code, out = _run_cli(
        ["validate", str(input_file), "--schema", "Trade", "--format", "xml"],
    )
    assert code == 2
    assert "Unsupported --format" in out


def test_cli_validate_runtime_error_missing_file() -> None:
    code, out = _run_cli(["validate", "missing.csv", "--schema", "Trade"])
    assert code == 3
    assert "Input file not found" in out


def test_cli_validate_output_files(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    html_file = tmp_path / "report.html"
    json_file = tmp_path / "report.json"
    _write_trade_csv(input_file)

    code, _out = _run_cli(
        [
            "validate",
            str(input_file),
            "--schema",
            "Trade",
            "--output",
            str(html_file),
            "--output-json",
            str(json_file),
        ],
    )
    assert code == 0
    assert html_file.exists()
    assert json_file.exists()


def test_cli_check_batch(tmp_path: Path) -> None:
    batch = tmp_path / "ids.txt"
    batch.write_text("US0378331005\nUS0378331009\n", encoding="utf-8")
    code, out = _run_cli(["check", "isin", "--batch", str(batch), "--no-color"])
    assert code == 1
    assert "Total: 2" in out


def test_cli_check_missing_value_usage_error() -> None:
    code, out = _run_cli(["check", "isin", "--no-color"])
    assert code == 2
    assert "requires <value> or --batch <file>" in out


def test_cli_check_batch_missing_file_runtime_error() -> None:
    code, out = _run_cli(["check", "isin", "--batch", "missing.txt", "--no-color"])
    assert code == 3
    assert "Batch file not found" in out


def test_cli_check_currency_and_business_date() -> None:
    currency_code, currency_out = _run_cli(["check", "currency", "EUR", "--no-color"])
    date_code, date_out = _run_cli(["check", "business-date", "2026-03-19", "--no-color"])
    assert currency_code == 0
    assert "Valid CurrencyCode" in currency_out
    assert date_code == 0
    assert "Valid BusinessDate" in date_out


def test_cli_validate_verbose_min_score_and_truncation(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    rows = [
        "trade_id,isin,side,quantity,price,currency,trade_date,settlement_date",
        *[f"T-{i},US0378331009,BUY,100,178.52,USD,2026-03-19,2026-03-20" for i in range(1, 25)],
    ]
    input_file.write_text("\n".join(rows) + "\n", encoding="utf-8")

    code, out = _run_cli(
        [
            "validate",
            str(input_file),
            "--schema",
            "Trade",
            "--verbose",
            "--min-score",
            "0.99",
        ]
    )
    assert code == 1
    assert "row=0" in out
    assert "truncated" in out


def test_cli_validate_unsupported_schema_usage_error(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    _write_trade_csv(input_file)

    code, out = _run_cli(["validate", str(input_file), "--schema", "Foo"])
    assert code == 2
    assert "Unsupported schema" in out


def test_cli_validate_jsonl_parse_errors(tmp_path: Path) -> None:
    bad_json = tmp_path / "bad.jsonl"
    bad_json.write_text("{bad json}\n", encoding="utf-8")

    code_bad, out_bad = _run_cli(["validate", str(bad_json), "--schema", "Trade"])
    assert code_bad == 3
    assert "Invalid JSON on line 1" in out_bad

    non_object = tmp_path / "non_object.jsonl"
    non_object.write_text('"hello"\n', encoding="utf-8")
    code_non_obj, out_non_obj = _run_cli(["validate", str(non_object), "--schema", "Trade"])
    assert code_non_obj == 3
    assert "must be a JSON object" in out_non_obj


def test_cli_validate_auto_format_detection_error(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.txt"
    input_file.write_text("ignored\n", encoding="utf-8")

    code, out = _run_cli(["validate", str(input_file), "--schema", "Trade"])
    assert code == 2
    assert "Could not detect format" in out
