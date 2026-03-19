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


def test_polars_clean_coerce_and_validate_rows() -> None:
    import polars as pl

    import finschema.integrations.polars  # noqa: F401

    frame = pl.DataFrame(
        {
            "trade_id": ["T-1", "T-2"],
            "isin": [" us0378331005 ", "US0378331009"],
            "side": ["BUY", "BUY"],
            "quantity": [100, 100],
            "price": [178.52, 178.52],
            "currency": [" usd ", "USD"],
            "trade_date": ["2026-03-19T12:00:00", "2026-03-19"],
            "settlement_date": ["2026-03-20", "2026-03-20"],
        }
    )

    coerced, coerce_report = frame.finschema.coerce("Trade")
    assert coerced["isin"].to_list()[0] == "US0378331005"
    assert coerced["currency"].to_list()[0] == "USD"
    assert any(issue.rule == "coerce_changes" for issue in coerce_report.info)

    cleaned, clean_report = coerced.finschema.clean("Trade")
    assert cleaned.height == 1
    assert cleaned["trade_id"].to_list() == ["T-1"]
    assert any(issue.rule == "clean_removed_rows" for issue in clean_report.info)

    rows = coerced["isin"].finschema.validate_rows(ISIN)
    assert [row.is_valid for row in rows] == [True, False]


def test_polars_lazyframe_and_expr_helpers() -> None:
    import polars as pl

    from finschema.integrations.polars import expr

    frame = pl.DataFrame(_trade_rows())
    lazy = frame.lazy()
    report = lazy.finschema.validate("Trade")
    mask = lazy.finschema.is_valid("Trade")
    assert report.stats["total_records"] == 2
    assert mask.to_list() == [True, False]

    flagged = frame.with_columns(valid_isin=expr.is_valid_isin("isin"))
    assert flagged["valid_isin"].to_list() == [True, False]
