# finschema

[![CI](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/finschema.svg)](https://pypi.org/project/finschema/)
[![Coverage](https://img.shields.io/badge/coverage-90%25+-brightgreen.svg)](https://github.com/tkrenn12306/finschema/actions)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./LICENSE)

Financial validation types, schemas, quality engine, and ecosystem integrations for Python.

## Project Status

Current release line: **`v0.6.0 Integrations Rollup`**

## Install

```bash
pip install finschema
```

Optional extras:

```bash
pip install "finschema[pandas]"
pip install "finschema[polars]"
pip install "finschema[fastapi]"
pip install "finschema[yaml]"
```

## Feature Matrix

| Area | Status | Highlights |
|---|---|---|
| Core Types | ✅ | ISIN/CUSIP/SEDOL/LEI/IBAN/BIC + FIGI/VALOR/WKN/RIC/Ticker, Country/Currency, Money/Price/Quantity/Percentage |
| Schemas | ✅ | Trade, Position, Portfolio + extended v0.5 schema set |
| Quality Engine | ✅ | Built-in rule packs, custom rules, strict/soft mode, TOML/YAML/pyproject config |
| Pandas | ✅ | `.validate()`, `.is_valid()`, `.clean()`, `.coerce()`, `Series.validate_rows()`, `read_csv()` helper |
| Polars | ✅ | DataFrame/Series/LazyFrame parity + expression validators (`expr.is_valid_isin`) |
| FastAPI | ✅ | Middleware auto-validation, quality headers, structured 422s, dependency helper |
| CLI | ✅ | `check`, `validate` (csv/json/jsonl/parquet), `diff`, `--watch`, HTML/JSON report outputs |
| HTML Reports | ✅ | Standalone single-file report, filter/sort, score gauge, invalid-row CSV export |

## Quick Start

```python
from finschema.types import ISIN, Money, CountryCode, CurrencyCode
from finschema.quality import ValidationEngine

isin = ISIN("US0378331005")
money = Money("1000.50", "EUR")
country = CountryCode("DEU")
currency = CurrencyCode("JPY")
report = ValidationEngine().validate(
    [{"trade_id": "T-1", "isin": "US0378331005", "side": "BUY", "quantity": 10, "price": 10.5, "currency": "USD", "trade_date": "2026-03-19", "settlement_date": "2026-03-20"}],
    schema="Trade",
)

print(isin, money, country.alpha2, currency.decimals, report.score)
```

## CLI

```bash
finschema check isin US0378331005
finschema check isin --batch identifiers.txt
finschema validate trades.csv --schema Trade --output report.html
finschema validate trades.json --schema Trade --config finschema.toml --watch
finschema diff trades_day1.csv trades_day2.csv --schema Trade --output-json diff.json
```

## Integrations

```python
# Pandas
import pandas as pd
import finschema.integrations.pandas  # registers .finschema

df = pd.read_csv("trades.csv")
clean_df, report = df.finschema.clean("Trade")

# Polars
import polars as pl
import finschema.integrations.polars  # registers .finschema
from finschema.integrations.polars import expr

pf = pl.read_csv("trades.csv")
pf = pf.filter(expr.is_valid_isin("isin"))
```

```python
# FastAPI
from fastapi import FastAPI
from finschema.integrations.fastapi import FinschemaMiddleware
from finschema.schemas import Trade

app = FastAPI()
app.add_middleware(FinschemaMiddleware, strict=True)

@app.post("/trades")
async def create_trade(trade: Trade) -> dict[str, str]:
    return {"trade_id": trade.trade_id}
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
