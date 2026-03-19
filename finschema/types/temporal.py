"""Temporal types."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from finschema.errors import InvalidFormatError, NotBusinessDayError


class BusinessDate(date):
    """Date constrained to weekdays for alpha default behavior."""

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
                    details={"year": value, "month": month, "day": day},
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
                    details={"expected": "YYYY-MM-DD", "input": value},
                ) from exc
        else:
            raise InvalidFormatError(
                "BusinessDate requires a date or ISO date string",
                details={"input_type": type(value).__name__},
            )

        if parsed.weekday() >= 5:
            next_business = parsed
            while next_business.weekday() >= 5:
                next_business += timedelta(days=1)
            prev_business = parsed
            while prev_business.weekday() >= 5:
                prev_business -= timedelta(days=1)
            raise NotBusinessDayError(
                f"{parsed.isoformat()} is not a business day",
                details={
                    "date": parsed.isoformat(),
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
                details={"input_type": type(value).__name__},
            )

        return core_schema.no_info_plain_validator_function(_validate)
