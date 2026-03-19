# finschema

[![CI](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tkrenn12306/finschema/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](./pyproject.toml)
[![Status](https://img.shields.io/badge/status-beta-yellow.svg)](#project-status)

Pydantic-compatible financial types, schemas, and quality validation.

## Project Status

Current release line: **`v0.2.0 Beta`**

Implemented in this version:
- `finschema.types`: identifiers + `Money`, `Price`, `Quantity`, `Percentage`, `NAV`, `BusinessDate`
- `finschema.schemas`: `Trade`, `Position`, `Portfolio`
- `finschema.quality`: `ValidationEngine`, `QualityReport`, built-in price/FX/portfolio rules
- `finschema check <type> <value>` CLI

Planned next:
- `v0.3.0`: DataFrame integrations and richer reporting UX

## Installation

`finschema` is currently installed from source.

```bash
git clone git@github.com:tkrenn12306/finschema.git
cd finschema
python3 -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Quickstart

### 1) Financial types

```python
from finschema.types import ISIN, Money, BusinessDate

ISIN("US0378331005")
Money(1000, "EUR")
BusinessDate("2026-03-19")
```

### 2) Schemas

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

### 3) Quality engine

```python
from finschema.quality import ValidationEngine

engine = ValidationEngine()
report = engine.validate(trade, schema="Trade")

print(report.score)
print(report.passed)
print(report.to_dict()["stats"])
```

### 4) Custom quality rule

```python
from finschema.quality import Severity, ValidationEngine, rule

@rule(name="max_single_name", severity=Severity.WARNING)
def max_single_name(portfolio):
    findings = []
    for position in portfolio.positions:
        if position.weight and position.weight.as_decimal > 0.20:
            findings.append(f"{position.isin} exceeds 20%")
    return findings

engine = ValidationEngine()
engine.add_rule(max_single_name)
```

### 5) CLI

```bash
finschema check isin US0378331005
finschema check lei 529900T8BM49AURSDO55
```

## Development

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
  types/         # implemented
  schemas/       # implemented (beta)
  quality/       # implemented (beta)
  reference/     # static offline datasets
  cli/           # implemented
  integrations/  # scaffold for next phases
```

## License

MIT
