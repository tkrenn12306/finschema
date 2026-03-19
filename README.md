# finschema

[![CI](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./pyproject.toml)
[![Status](https://img.shields.io/badge/status-v0.3.0%20integrations-brightgreen.svg)](#project-status)

Pydantic-compatible financial types, schemas, quality rules, and ecosystem integrations.

## Project Status

Current release line: **`v0.3.0 Integrations`**

Implemented in this version:
- `finschema.types`: financial identifiers, monetary and temporal primitives
- `finschema.schemas`: `Trade`, `Position`, `Portfolio`
- `finschema.quality`: `ValidationEngine`, `QualityReport`, custom rule decorator
- `finschema.integrations`: Pandas accessor, Polars namespace, FastAPI middleware
- `finschema` CLI: `check` and `validate` commands

## Installation

```bash
git clone git@github.com:tkrenn12306/finschema.git
cd finschema
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

Optional extras:

```bash
pip install -e .[pandas]
pip install -e .[polars]
pip install -e .[fastapi]
```

## Quickstart

### 1) Type and schema validation

```python
from finschema.schemas import Trade

trade = Trade(
    trade_id="T-20260319-001",
    isin="US0378331005",
    side="BUY",
    quantity=100,
    price=178.52,
    currency="USD",
    trade_date="2026-03-19",
    settlement_date="2026-03-20",
)
```

### 2) Quality engine and reports

```python
from finschema.quality import ValidationEngine

engine = ValidationEngine()
report = engine.validate(trade, schema="Trade")

report.to_dict()
report.to_json("report.json")
report.to_html("report.html")
```

### 3) Pandas integration

```python
import pandas as pd
import finschema.integrations.pandas  # registers .finschema accessor

df = pd.DataFrame([{
    "trade_id": "T-1",
    "isin": "US0378331005",
    "side": "BUY",
    "quantity": 10,
    "price": 100,
    "currency": "USD",
    "trade_date": "2026-03-19",
    "settlement_date": "2026-03-20",
}])

report = df.finschema.validate("Trade")
mask = df.finschema.is_valid("Trade")
clean_df = df[mask]
```

### 4) FastAPI middleware

```python
from fastapi import FastAPI
from finschema.integrations.fastapi import FinschemaMiddleware
from finschema.schemas import Trade

app = FastAPI()
app.add_middleware(FinschemaMiddleware, strict=True)

@app.post("/trades")
async def create_trade(trade: Trade) -> dict[str, str]:
    return {"trade_id": trade.trade_id, "status": "accepted"}
```

### 5) CLI

```bash
finschema check isin US0378331005
finschema validate trades.csv --schema Trade --output report.html --output-json report.json
finschema validate positions.parquet --schema Position --format parquet
finschema validate trades.jsonl --schema Trade --verbose
```

## Development

```bash
ruff check .
ruff format --check .
mypy
pytest
coverage report --include="finschema/types/*" --fail-under=95
```

## License

MIT
