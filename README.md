# finschema

Pydantic-compatible financial types and validation utilities.

## Alpha Scope (`0.1.0`)

- Financial identifier types: `ISIN`, `CUSIP`, `SEDOL`, `LEI`, `IBAN`, `BIC`
- Market and monetary types: `CurrencyCode`, `Money`
- Temporal type: `BusinessDate`
- CLI: `finschema check <type> <value>`

## Install

```bash
pip install finschema
```

## Quickstart

```python
from finschema.types import ISIN, Money

ISIN("US0378331005")
Money(100, "EUR")
```

```bash
finschema check isin US0378331005
```
