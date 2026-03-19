from __future__ import annotations

import importlib.util

import pytest

from finschema.schemas import Trade
from finschema.types import ISIN

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("pandas") is None,
    reason="pandas not installed",
)


def _trade_rows() -> list[dict[str, object]]:
    return [
        {
            "trade_id": "T-1",
            "isin": "US0378331005",
            "side": "BUY",
            "quantity": 100,
            "price": 178.52,
            "currency": "USD",
            "trade_date": "2026-03-19",
            "settlement_date": "2026-03-20",
        },
        {
            "trade_id": "T-2",
            "isin": "US0378331009",
            "side": "BUY",
            "quantity": 100,
            "price": 178.52,
            "currency": "USD",
            "trade_date": "2026-03-19",
            "settlement_date": "2026-03-20",
        },
    ]


def test_dataframe_validate_accepts_schema_name_and_type() -> None:
    import pandas as pd

    import finschema.integrations.pandas  # noqa: F401

    frame = pd.DataFrame(_trade_rows())
    report_name = frame.finschema.validate("Trade")
    report_type = frame.finschema.validate(Trade)
    assert report_name.stats["total_records"] == 2
    assert report_type.stats["total_records"] == 2
    assert len(report_name.errors) >= 1


def test_dataframe_is_valid_returns_boolean_series() -> None:
    import pandas as pd

    import finschema.integrations.pandas  # noqa: F401

    frame = pd.DataFrame(_trade_rows())
    mask = frame.finschema.is_valid("Trade")
    assert mask.dtype == bool
    assert mask.tolist() == [True, False]


def test_series_validate_callable_validator() -> None:
    import pandas as pd

    import finschema.integrations.pandas  # noqa: F401

    series = pd.Series(["US0378331005", "US0378331009"], name="isin")
    report = series.finschema.validate(ISIN)
    assert report.stats["total_records"] == 2
    assert len(report.errors) == 1


def test_series_is_valid_callable_validator() -> None:
    import pandas as pd

    import finschema.integrations.pandas  # noqa: F401

    series = pd.Series(["US0378331005", "US0378331009"], name="isin")
    mask = series.finschema.is_valid(ISIN)
    assert mask.tolist() == [True, False]
