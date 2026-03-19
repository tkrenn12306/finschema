"""Temporal types."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from finschema.errors import InvalidFormatError, NotBusinessDayError, OutOfRangeError

from ._pydantic import PydanticStrMixin


class BusinessDate(date):
    """Date constrained to weekdays for default US business-day behavior."""

    JSON_SCHEMA_TITLE = "BusinessDate"
    JSON_SCHEMA_FORMAT = "date"
    JSON_SCHEMA_EXAMPLES = ("2026-03-19",)

    def __new__(
        cls,
        value: str | date | int,
        month: int | None = None,
        day: int | None = None,
    ) -> BusinessDate:
        if isinstance(value, int):
            if month is None or day is None:
                raise InvalidFormatError(
                    "BusinessDate requires year, month, and day for integer constructor",
                    field="date",
                    expected="year, month, day",
                    actual={"year": value, "month": month, "day": day},
                )
            parsed = date(value, month, day)
        elif isinstance(value, date):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = date.fromisoformat(value)
            except ValueError as exc:
                raise InvalidFormatError(
                    f"{value!r} is not a valid ISO date",
                    field="date",
                    expected="YYYY-MM-DD",
                    actual=value,
                ) from exc
        else:
            raise InvalidFormatError(
                "BusinessDate requires a date or ISO date string",
                field="date",
                expected="date or ISO string",
                actual=type(value).__name__,
            )

        if parsed.weekday() >= 5:
            next_business = parsed
            while next_business.weekday() >= 5:
                next_business += timedelta(days=1)
            prev_business = parsed
            while prev_business.weekday() >= 5:
                prev_business -= timedelta(days=1)
            day_name = parsed.strftime("%A")
            raise NotBusinessDayError(
                f"{parsed.isoformat()} is a {day_name}",
                field="date",
                expected="weekday (Mon-Fri)",
                actual=parsed.isoformat(),
                details={
                    "next_business_day": next_business.isoformat(),
                    "prev_business_day": prev_business.isoformat(),
                    "calendar": "US",
                },
            )

        return date.__new__(cls, parsed.year, parsed.month, parsed.day)

    @classmethod
    def __get_pydantic_core_schema__(cls, _source_type: Any, _handler: Any) -> Any:
        from pydantic_core import core_schema

        def _validate(value: Any) -> BusinessDate:
            if isinstance(value, BusinessDate):
                return value
            if isinstance(value, date):
                return cls(value)
            if isinstance(value, str):
                return cls(value)
            raise InvalidFormatError(
                "BusinessDate requires a date or ISO date string",
                field="date",
                expected="date or ISO string",
                actual=type(value).__name__,
            )

        return core_schema.no_info_plain_validator_function(_validate)

    @classmethod
    def __get_pydantic_json_schema__(cls, _core_schema: Any, _handler: Any) -> dict[str, Any]:
        return {
            "type": "string",
            "title": cls.JSON_SCHEMA_TITLE,
            "format": cls.JSON_SCHEMA_FORMAT,
            "examples": list(cls.JSON_SCHEMA_EXAMPLES),
            "description": "Weekday-only date (Mon-Fri).",
        }


_TENOR_DAYS: dict[str, int] = {
    "ON": 1,
    "TN": 2,
    "SN": 3,
    "1D": 1,
    "1W": 7,
    "2W": 14,
    "1M": 30,
    "2M": 60,
    "3M": 90,
    "6M": 180,
    "9M": 270,
    "1Y": 365,
    "2Y": 730,
    "3Y": 1095,
    "5Y": 1825,
    "7Y": 2555,
    "10Y": 3650,
    "15Y": 5475,
    "20Y": 7300,
    "30Y": 10950,
}


class Tenor(PydanticStrMixin, str):
    def __new__(cls, value: str) -> Tenor:
        normalized = value.upper().strip()
        if normalized not in _TENOR_DAYS:
            raise InvalidFormatError(
                f"{normalized!r} is not a supported tenor",
                field="tenor",
                expected=sorted(_TENOR_DAYS.keys()),
                actual=normalized,
            )
        return str.__new__(cls, normalized)

    @property
    def label(self) -> str:
        return str(self)

    @property
    def days(self) -> int:
        return _TENOR_DAYS[str(self)]


class MaturityDate(BusinessDate):
    def __new__(cls, value: str | date, *, reference_date: date | None = None) -> MaturityDate:
        parsed = BusinessDate(value)
        ref = reference_date or date.today()
        if parsed <= ref:
            raise OutOfRangeError(
                "MaturityDate must be in the future",
                field="maturity_date",
                expected=f"> {ref.isoformat()}",
                actual=parsed.isoformat(),
                details={"reference_date": ref.isoformat()},
            )
        return date.__new__(cls, parsed.year, parsed.month, parsed.day)
