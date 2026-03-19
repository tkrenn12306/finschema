from __future__ import annotations

from collections.abc import Callable

import typer

from finschema.errors import ValidationError
from finschema.types import BIC, CUSIP, IBAN, ISIN, LEI, SEDOL, BusinessDate, CurrencyCode

app = typer.Typer(help="finschema alpha CLI")

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


@app.callback()
def main_callback() -> None:
    """finschema alpha CLI."""


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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
