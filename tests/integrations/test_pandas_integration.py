from __future__ import annotations

import importlib.util
from pathlib import Path

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


def test_dataframe_clean_and_coerce() -> None:
    import pandas as pd

    import finschema.integrations.pandas  # noqa: F401

    frame = pd.DataFrame(
        [
            {
                "trade_id": "T-1",
                "isin": " us0378331005 ",
                "side": "BUY",
                "quantity": 100,
                "price": 178.52,
                "currency": " usd ",
                "trade_date": "2026-03-19T12:00:00",
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
    )

    coerced, coerce_report = frame.finschema.coerce("Trade")
    assert coerced.loc[0, "isin"] == "US0378331005"
    assert coerced.loc[0, "currency"] == "USD"
    assert coerced.loc[0, "trade_date"] == "2026-03-19"
    assert any(issue.rule == "coerce_changes" for issue in coerce_report.info)

    cleaned, clean_report = coerced.finschema.clean("Trade")
    assert len(cleaned) == 1
    assert cleaned.iloc[0]["trade_id"] == "T-1"
    assert any(issue.rule == "clean_removed_rows" for issue in clean_report.info)


def test_series_validate_rows_reports_per_index() -> None:
    import pandas as pd

    import finschema.integrations.pandas  # noqa: F401

    series = pd.Series(["US0378331005", "US0378331009"], name="isin")
    rows = series.finschema.validate_rows(ISIN)
    assert [row.is_valid for row in rows] == [True, False]
    assert rows[1].errors


def test_read_csv_helper(tmp_path: Path) -> None:
    from finschema.integrations.pandas import read_csv

    csv_path = tmp_path / "trades.csv"
    csv_path.write_text(
        "trade_id,isin,side,quantity,price,currency,trade_date,settlement_date\n"
        "T-1,US0378331005,BUY,100,178.52,USD,2026-03-19,2026-03-20\n",
        encoding="utf-8",
    )

    frame, report = read_csv(csv_path, schema="Trade")
    assert len(frame) == 1
    assert report.passed is True
