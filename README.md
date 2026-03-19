# finschema

[![CI](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./pyproject.toml)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](#project-status)

Pydantic-compatible financial types and validation utilities.

`finschema` brings domain-aware validation to financial data:
- Identifier checks (`ISIN`, `CUSIP`, `SEDOL`, `LEI`, `IBAN`, `BIC`)
- Currency-safe money operations (`Money`, `CurrencyCode`)
- Business-day validation (`BusinessDate`)
- CLI checks for fast validation from terminal

## Project Status

Current release line: **`v0.1.0 Alpha`**

Implemented now:
- `finschema.types`: `ISIN`, `CUSIP`, `SEDOL`, `LEI`, `IBAN`, `BIC`, `CurrencyCode`, `Money`, `BusinessDate`
- `finschema check <type> <value>` CLI
- Strict CI gates (`ruff`, `mypy`, `pytest`, coverage)

Planned for next phases:
- `v0.2.0`: `schemas/` + initial `quality/` engine
- `v0.3.0+`: integrations (`pandas`, `polars`, `fastapi`), richer reporting

## Installation

`finschema` is currently in alpha and installed from source.

### Option A: Editable install (recommended for contributors)

```bash
git clone git@github.com:tkrenn12306/finschema.git
cd finschema
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

### Option B: Runtime install only

```bash
git clone git@github.com:tkrenn12306/finschema.git
cd finschema
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Note: A public PyPI release is planned for a later stable milestone.

## Quickstart

### 1) Validate a single identifier

```python
from finschema.types import ISIN

ISIN("US0378331005")
```

Invalid value raises a structured error:

```python
from finschema.types import ISIN

ISIN("US0378331009")
# finschema.errors.CheckDigitError:
# Invalid ISIN check digit
#   identifier: 'US0378331009'
#   expected: 5
#   actual: 9
#   algorithm: 'Luhn (ISO 6166)'
```

### 2) Currency-safe money

```python
from finschema.types import Money

eur = Money(100, "EUR")
usd = Money(50, "USD")

eur + usd  # raises CurrencyMismatchError
```

### 3) Business day checks

```python
from finschema.types import BusinessDate

BusinessDate("2026-03-19")  # valid weekday
BusinessDate("2026-03-21")  # raises NotBusinessDayError (Saturday)
```

### 4) CLI checks

```bash
finschema check isin US0378331005
finschema check lei 529900T8BM49AURSDO55
finschema check iban DE89370400440532013000
```

## Pydantic Integration

All alpha types are Pydantic v2-compatible:

```python
from pydantic import BaseModel
from finschema.types import ISIN, BusinessDate, Money

class TradeIn(BaseModel):
    isin: ISIN
    trade_date: BusinessDate
    notional: Money
```

## Development

Setup:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Quality gates:

```bash
ruff check .
ruff format --check .
mypy
pytest
coverage report --include="finschema/types/*" --fail-under=95
```

## Repository Layout

```text
finschema/
  types/         # alpha implemented
  reference/     # alpha implemented (offline datasets)
  cli/           # alpha implemented
  schemas/       # scaffold for v0.2.0+
  quality/       # scaffold for v0.2.0+
  integrations/  # scaffold for v0.3.0+
```

## Contributing

Contributions are welcome. For alpha:
- keep API changes explicit and documented
- add tests for all behavior changes
- keep `ruff`, `mypy`, and `pytest` green

## License

MIT (see project metadata in `pyproject.toml`).
