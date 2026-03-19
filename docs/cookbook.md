# Cookbook

This page contains practical workflows for common integrations.

## 1. Validate Trades in Pandas

```python
import pandas as pd
import finschema.integrations.pandas  # registers accessor

frame = pd.read_csv("trades.csv")
report = frame.finschema.validate("Trade")
print(report.score, report.passed)
```

## 2. Keep Only Valid Pandas Rows

```python
import pandas as pd
import finschema.integrations.pandas

frame = pd.read_csv("trades.csv")
cleaned, report = frame.finschema.clean("Trade")
print(len(frame), len(cleaned), len(report.errors))
```

## 3. Coerce Typical Data Issues in Pandas

```python
import pandas as pd
import finschema.integrations.pandas

frame = pd.DataFrame({"isin": [" us0378331005 "], "currency": [" usd "]})
coerced, report = frame.finschema.coerce("Trade")
print(coerced.iloc[0].to_dict())
```

## 4. Validate a Single Pandas Column

```python
import pandas as pd
import finschema.integrations.pandas
from finschema.types import ISIN

series = pd.Series(["US0378331005", "US0378331009"], name="isin")
rows = series.finschema.validate_rows(ISIN)
print(rows[0].is_valid, rows[1].errors)
```

## 5. Validate Polars DataFrame

```python
import polars as pl
import finschema.integrations.polars  # registers accessor

frame = pl.read_csv("trades.csv")
mask = frame.finschema.is_valid("Trade")
print(mask)
```

## 6. Use Polars Expression Validators

```python
import polars as pl
from finschema.integrations.polars import expr

frame = pl.read_csv("trades.csv")
valid_only = frame.filter(expr.is_valid_isin("isin"))
```

## 7. Validate FastAPI Request Bodies with Middleware

```python
from fastapi import FastAPI
from finschema.integrations.fastapi import FinschemaMiddleware
from finschema.schemas import Trade

app = FastAPI()
app.add_middleware(FinschemaMiddleware, strict=True)

@app.post("/trades")
async def create_trade(trade: Trade):
    return {"trade_id": trade.trade_id}
```

## 8. Validate FastAPI with Dependency Helper

```python
from fastapi import Depends, FastAPI
from finschema.integrations.fastapi import depends_validate

app = FastAPI()

@app.post("/trade-payload")
async def payload_only(payload=Depends(depends_validate("Trade", strict=False))):
    return payload
```

## 9. Run CLI Quality Gate in CI

```bash
finschema validate data/trades.csv --schema Trade --min-score 0.95 --output-json report.json
```

Exit code is `0` for pass, `1` for quality fail, `2` for usage error, `3` for runtime/dependency/IO errors.

## 10. Compare Two Snapshots with CLI Diff

```bash
finschema diff data/trades_day1.csv data/trades_day2.csv --schema Trade --output-json diff.json
```

## 11. Generate Standalone HTML Reports

```python
from finschema.quality import ValidationEngine

engine = ValidationEngine()
report = engine.validate([], schema="Trade")
report.to_html("quality_report.html")
```

## 12. Watch Mode During Data Preparation

```bash
finschema validate data/staging_trades.jsonl --schema Trade --watch --watch-interval 0.5
```
