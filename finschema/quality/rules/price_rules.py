"""Price plausibility rule set."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from finschema.quality.report import Severity, ValidationIssue


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _as_decimal(value: Any) -> Decimal:
    if hasattr(value, "as_decimal"):
        return Decimal(str(value.as_decimal))
    if hasattr(value, "value"):
        return Decimal(str(value.value))
    return Decimal(str(value))


def validate_price(
    record: Any,
    *,
    record_index: int | None,
    config: dict[str, Any],
    context: dict[str, Any],
) -> list[ValidationIssue]:
    price = _get(record, "price")
    if price is None:
        return []

    issues: list[ValidationIssue] = []
    price_value = _as_decimal(price)

    price_min = Decimal(str(config.get("price_min", 0)))
    if price_value <= price_min:
        issues.append(
            ValidationIssue(
                rule="positive_price",
                severity=Severity.ERROR,
                message=f"Price must be > {price_min}, got {price_value}",
                field="price",
                record_index=record_index,
            )
        )

    asset_class_raw = _get(record, "asset_class")
    if asset_class_raw is not None:
        asset_class = str(getattr(asset_class_raw, "value", asset_class_raw))
        bounds = config.get("price_max_by_asset_class", {})
        max_value_raw = bounds.get(asset_class)
        if max_value_raw is not None:
            max_value = Decimal(str(max_value_raw))
            if price_value > max_value:
                issues.append(
                    ValidationIssue(
                        rule="price_within_bounds",
                        severity=Severity.ERROR,
                        message=(f"Price {price_value} exceeds max {max_value} for {asset_class}"),
                        field="price",
                        record_index=record_index,
                    )
                )

    previous_prices = context.get("previous_prices", {})
    isin_value = _get(record, "isin")
    key = str(isin_value) if isin_value is not None else None
    if key and isinstance(previous_prices, dict) and key in previous_prices:
        previous = Decimal(str(previous_prices[key]))
        if previous > 0:
            change = abs(price_value - previous) / previous
            max_change = Decimal(str(config.get("price_daily_change_max", 0.25)))
            if change > max_change:
                issues.append(
                    ValidationIssue(
                        rule="price_daily_change_limit",
                        severity=Severity.WARNING,
                        message=(f"Price changed by {change:.4f} vs limit {max_change:.4f}"),
                        field="price",
                        record_index=record_index,
                        context={"change": str(change), "limit": str(max_change)},
                    )
                )

    stale_threshold = int(config.get("stale_price_days", 3))
    stale_by_isin = context.get("stale_price_days_by_isin", {})
    stale_days_raw = None
    if key and isinstance(stale_by_isin, dict):
        stale_days_raw = stale_by_isin.get(key)
    if stale_days_raw is None and isinstance(context.get("stale_price_days"), int):
        stale_days_raw = context.get("stale_price_days")
    if stale_days_raw is not None:
        stale_days = int(stale_days_raw)
        if stale_days >= stale_threshold:
            issues.append(
                ValidationIssue(
                    rule="stale_price_detection",
                    severity=Severity.WARNING,
                    message=(
                        f"Price appears stale for {stale_days} days (threshold {stale_threshold})"
                    ),
                    field="price",
                    record_index=record_index,
                    context={"stale_days": stale_days, "threshold": stale_threshold},
                )
            )

    return issues
