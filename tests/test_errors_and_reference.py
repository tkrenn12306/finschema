from __future__ import annotations

import pytest

from finschema.errors import FinschemaError, InvalidCurrencyError
from finschema.reference.currencies import get_currency_decimals


def test_error_string_includes_details() -> None:
    err = FinschemaError("boom", details={"field": "isin", "expected": 5})
    text = str(err)
    assert "boom" in text
    assert "field" in text
    assert "expected" in text


def test_get_currency_decimals_rejects_unknown() -> None:
    with pytest.raises(InvalidCurrencyError):
        get_currency_decimals("XXX")
