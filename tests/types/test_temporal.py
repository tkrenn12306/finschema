from __future__ import annotations

from datetime import date

import pytest
from pydantic import TypeAdapter
from pydantic import ValidationError as PydanticValidationError

from finschema.errors import InvalidFormatError, NotBusinessDayError
from finschema.types import BusinessDate


def test_business_date_weekday() -> None:
    value = BusinessDate("2026-03-19")
    assert value.isoformat() == "2026-03-19"


def test_business_date_weekend_rejected() -> None:
    with pytest.raises(NotBusinessDayError) as exc:
        BusinessDate("2026-03-21")
    assert exc.value.details["next_business_day"] == "2026-03-23"
    assert exc.value.details["prev_business_day"] == "2026-03-20"


def test_business_date_invalid_format() -> None:
    with pytest.raises(InvalidFormatError):
        BusinessDate("2026/03/21")


def test_business_date_accepts_date_instance() -> None:
    value = BusinessDate(date(2026, 3, 19))
    assert value.isoformat() == "2026-03-19"


def test_business_date_invalid_type() -> None:
    with pytest.raises(InvalidFormatError):
        BusinessDate(123)  # type: ignore[arg-type]


def test_business_date_type_adapter_paths() -> None:
    adapter = TypeAdapter(BusinessDate)
    value = BusinessDate("2026-03-19")
    assert adapter.validate_python(value) == value
    assert adapter.validate_python(date(2026, 3, 20)).isoformat() == "2026-03-20"
    with pytest.raises(PydanticValidationError):
        adapter.validate_python(123)
