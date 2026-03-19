# Getting Started

## Install

```bash
pip install finschema
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
```
