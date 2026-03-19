"""Identifier format/check-digit rules."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from finschema.errors import (
    CheckDigitError,
    InvalidCountryError,
    InvalidFormatError,
    ValidationError,
)
from finschema.quality.report import Severity, ValidationIssue
from finschema.types import BIC, CUSIP, FIGI, IBAN, ISIN, LEI, SEDOL, VALOR, WKN

_VALIDATORS: dict[str, Callable[[str], Any]] = {
    "isin": ISIN,
    "cusip": CUSIP,
    "sedol": SEDOL,
    "lei": LEI,
    "counterparty_lei": LEI,
    "iban": IBAN,
    "bic": BIC,
    "figi": FIGI,
    "valor": VALOR,
    "wkn": WKN,
}


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def validate_identifiers(
    record: Any,
    *,
    record_index: int | None,
    config: dict[str, Any],
    context: dict[str, Any],
) -> list[ValidationIssue]:
    del config
    del context

    issues: list[ValidationIssue] = []
    for field_name, validator in _VALIDATORS.items():
        value = _get(record, field_name)
        if value is None:
            continue
        try:
            validator(str(value))
        except CheckDigitError as exc:
            issues.append(
                ValidationIssue(
                    rule="check_digit_valid",
                    severity=Severity.ERROR,
                    message=exc.message,
                    field=field_name,
                    record_index=record_index,
                    context={"identifier_type": validator.__name__},
                )
            )
        except (InvalidFormatError, InvalidCountryError, ValidationError) as exc:
            issues.append(
                ValidationIssue(
                    rule="format_valid",
                    severity=Severity.ERROR,
                    message=exc.message,
                    field=field_name,
                    record_index=record_index,
                    context={"identifier_type": validator.__name__},
                )
            )

    return issues
