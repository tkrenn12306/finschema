# Getting Started

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

## Quick Example

```python
from finschema.types import ISIN, Money, CurrencyCode

ISIN("US0378331005")
Money("1000.50", CurrencyCode("EUR"))
```

## CLI

```bash
finschema check isin US0378331005
finschema check isin --batch ids.txt
finschema validate trades.csv --schema Trade --output report.html
finschema diff trades_day1.csv trades_day2.csv --schema Trade
```
