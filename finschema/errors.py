from __future__ import annotations

from typing import Any


class FinschemaError(ValueError):
    """Base error with normalized structured details."""

    default_code = "finschema_error"
    default_rule = "finschema.validation"

    def __init__(
        self,
        message: str,
        *,
        field: str | None = None,
        expected: Any = None,
        actual: Any = None,
        rule: str | None = None,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message

        normalized: dict[str, Any] = {
            "field": field,
            "expected": expected,
            "actual": actual,
            "rule": rule or self.default_rule,
            "code": code or self.default_code,
            "message": message,
        }
        if details:
            normalized.update(details)
            normalized.setdefault("field", field)
            normalized.setdefault("expected", expected)
            normalized.setdefault("actual", actual)
            normalized.setdefault("rule", rule or self.default_rule)
            normalized.setdefault("code", code or self.default_code)
            normalized.setdefault("message", message)

        self.details = normalized

    def __str__(self) -> str:
        if not self.details:
            return self.message
        detail_lines = [f"  {key}: {value!r}" for key, value in self.details.items()]
        return "\n".join([self.message, *detail_lines])

    def to_dict(self) -> dict[str, Any]:
        return dict(self.details)


class ValidationError(FinschemaError):
    """Generic validation error."""

    default_code = "validation_error"
    default_rule = "finschema.validation.generic"


class InvalidFormatError(ValidationError):
    default_code = "invalid_format"
    default_rule = "format.check"


class CheckDigitError(ValidationError):
    default_code = "check_digit_error"
    default_rule = "check_digit.verify"


class InvalidCountryError(ValidationError):
    default_code = "invalid_country"
    default_rule = "country.code"


class InvalidCurrencyError(ValidationError):
    default_code = "invalid_currency"
    default_rule = "currency.code"


class PrecisionError(ValidationError):
    default_code = "precision_error"
    default_rule = "precision.check"


class CurrencyMismatchError(ValidationError):
    default_code = "currency_mismatch"
    default_rule = "currency.match"


class NotBusinessDayError(ValidationError):
    default_code = "not_business_day"
    default_rule = "business_day.check"


class OutOfRangeError(ValidationError):
    default_code = "out_of_range"
    default_rule = "range.check"
