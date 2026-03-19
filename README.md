# finschema

[![CI](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/finschema.svg)](https://pypi.org/project/finschema/)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen.svg)](https://github.com/tkrenn12306/finschema/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

Financial validation types, schemas, and quality tooling for Python.

## Project Status

Current release line: **`v0.4.0 Full-Spec Rollup`**

## Install

```bash
pip install finschema
```

Optional extras:

```bash
pip install "finschema[pandas]"
pip install "finschema[polars]"
pip install "finschema[fastapi]"
```

## 60-Second Quickstart

```python
from finschema.types import ISIN, Money, CountryCode, CurrencyCode

isin = ISIN("US0378331005")
money = Money("1000.50", "EUR")
country = CountryCode("DEU")
currency = CurrencyCode("JPY")

print(isin, money, country.alpha2, currency.decimals)
```

## CLI

```bash
finschema check isin US0378331005
finschema check isin --batch identifiers.txt
finschema validate trades.csv --schema Trade --output report.html
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
ruff check .
ruff format --check .
mypy
pytest
```
