from __future__ import annotations

import importlib.util

import pytest

from finschema.types import ISIN

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("polars") is None,
    reason="polars not installed",
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


def test_polars_dataframe_validate_and_mask() -> None:
    import polars as pl

    import finschema.integrations.polars  # noqa: F401

    frame = pl.DataFrame(_trade_rows())
    report = frame.finschema.validate("Trade")
    mask = frame.finschema.is_valid("Trade")
    assert report.stats["total_records"] == 2
    assert len(report.errors) >= 1
    assert mask.to_list() == [True, False]


def test_polars_series_scalar_validation() -> None:
    import polars as pl

    import finschema.integrations.polars  # noqa: F401

    series = pl.Series("isin", ["US0378331005", "US0378331009"])
    report = series.finschema.validate(ISIN)
    mask = series.finschema.is_valid(ISIN)
    assert len(report.errors) == 1
    assert mask.to_list() == [True, False]
