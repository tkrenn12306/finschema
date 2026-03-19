from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FinschemaError(ValueError):
    """Base error with structured details for deterministic diagnostics."""

    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        if not self.details:
            return self.message
        detail_lines = [f"  {key}: {value!r}" for key, value in self.details.items()]
        return "\n".join([self.message, *detail_lines])


class ValidationError(FinschemaError):
    """Generic validation error."""


class InvalidFormatError(ValidationError):
    """Raised when a value does not match the required format."""


class CheckDigitError(ValidationError):
    """Raised when a check digit algorithm fails."""


class InvalidCountryError(ValidationError):
    """Raised when an unknown country code is encountered."""


class InvalidCurrencyError(ValidationError):
    """Raised when an unknown currency code is encountered."""


class PrecisionError(ValidationError):
    """Raised when an amount precision exceeds currency minor units."""


class CurrencyMismatchError(ValidationError):
    """Raised when arithmetic is attempted on two different currencies."""


class NotBusinessDayError(ValidationError):
    """Raised when a date is not a business day."""
