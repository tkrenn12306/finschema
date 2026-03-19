from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from finschema.cli.main import app

runner = CliRunner()


def test_cli_check_valid_isin() -> None:
    result = runner.invoke(app, ["check", "isin", "US0378331005"])
    assert result.exit_code == 0
    assert "US0378331005" in result.stdout


def test_cli_check_invalid_isin() -> None:
    result = runner.invoke(app, ["check", "isin", "US0378331009"])
    assert result.exit_code == 1
    assert "Invalid ISIN check digit" in result.stdout


def test_cli_unsupported_type() -> None:
    result = runner.invoke(app, ["check", "foo", "bar"])
    assert result.exit_code == 2
    assert "Unsupported type" in result.stdout


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "finschema CLI" in result.stdout


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

    result = runner.invoke(app, ["validate", str(input_file), "--schema", "Trade"])
    assert result.exit_code == 0
    assert "Schema: Trade" in result.stdout
    assert "PASS" in result.stdout


def test_cli_validate_csv_fail(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    _write_trade_csv(input_file, invalid_isin=True)

    result = runner.invoke(app, ["validate", str(input_file), "--schema", "Trade"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout


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

    result = runner.invoke(app, ["validate", str(input_file), "--schema", "Trade"])
    assert result.exit_code == 0


def test_cli_validate_usage_error(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    _write_trade_csv(input_file)

    result = runner.invoke(
        app,
        ["validate", str(input_file), "--schema", "Trade", "--format", "xml"],
    )
    assert result.exit_code == 2
    assert "Unsupported --format" in result.stdout


def test_cli_validate_runtime_error_missing_file() -> None:
    result = runner.invoke(app, ["validate", "missing.csv", "--schema", "Trade"])
    assert result.exit_code == 3
    assert "Input file not found" in result.stdout


def test_cli_validate_output_files(tmp_path: Path) -> None:
    input_file = tmp_path / "trades.csv"
    html_file = tmp_path / "report.html"
    json_file = tmp_path / "report.json"
    _write_trade_csv(input_file)

    result = runner.invoke(
        app,
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
    assert result.exit_code == 0
    assert html_file.exists()
    assert json_file.exists()
