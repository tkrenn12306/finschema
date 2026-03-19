"""FX consistency rule set."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from finschema.quality.report import Severity, ValidationIssue


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _lookup_pair(rates: dict[Any, Any], base: str, quote: str) -> Any:
    return rates.get((base, quote), rates.get(f"{base}/{quote}"))


def validate_fx(
    record: Any,
    *,
    record_index: int | None,
    config: dict[str, Any],
    context: dict[str, Any],
) -> list[ValidationIssue]:
    base = _get(record, "base")
    quote = _get(record, "quote")
    rate = _get(record, "rate")

    if base is None or quote is None or rate is None:
        return []

    base_code = str(base)
    quote_code = str(quote)
    rate_value = Decimal(str(rate))

    issues: list[ValidationIssue] = []

    if rate_value <= 0:
        issues.append(
            ValidationIssue(
                rule="fx_rate_positive",
                severity=Severity.ERROR,
                message=f"FX rate must be > 0, got {rate_value}",
                field="rate",
                record_index=record_index,
            )
        )

    if base_code == quote_code:
        issues.append(
            ValidationIssue(
                rule="fx_no_self_pair",
                severity=Severity.ERROR,
                message=f"Self FX pair {base_code}/{quote_code} is not allowed",
                field="base",
                record_index=record_index,
            )
        )

    reference_rates = context.get("fx_reference", {})
    if isinstance(reference_rates, dict):
        reference_raw = _lookup_pair(reference_rates, base_code, quote_code)
        if reference_raw is not None:
            reference = Decimal(str(reference_raw))
            if reference > 0:
                deviation = abs(rate_value - reference) / reference
                max_deviation = Decimal(str(config.get("fx_deviation_max", 0.05)))
                if deviation > max_deviation:
                    issues.append(
                        ValidationIssue(
                            rule="fx_deviation_limit",
                            severity=Severity.WARNING,
                            message=(
                                f"FX deviation {deviation:.4f} exceeds limit {max_deviation:.4f}"
                            ),
                            field="rate",
                            record_index=record_index,
                            context={"deviation": str(deviation), "limit": str(max_deviation)},
                        )
                    )

        inverse_raw = _get(
            record, "inverse_rate", _lookup_pair(reference_rates, quote_code, base_code)
        )
        if inverse_raw is not None:
            inverse_rate = Decimal(str(inverse_raw))
            if inverse_rate > 0:
                tolerance = Decimal(str(config.get("fx_inverse_tolerance", 0.02)))
                product_error = abs(rate_value * inverse_rate - Decimal("1"))
                if product_error > tolerance:
                    issues.append(
                        ValidationIssue(
                            rule="fx_inverse_consistency",
                            severity=Severity.WARNING,
                            message=(
                                f"FX pair inverse mismatch: {base_code}/{quote_code} * "
                                f"{quote_code}/{base_code} deviates by {product_error:.4f}"
                            ),
                            field="rate",
                            record_index=record_index,
                            context={"error": str(product_error), "tolerance": str(tolerance)},
                        )
                    )

    return issues
