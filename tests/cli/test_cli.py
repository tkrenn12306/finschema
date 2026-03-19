from __future__ import annotations

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
    assert "finschema alpha CLI" in result.stdout
