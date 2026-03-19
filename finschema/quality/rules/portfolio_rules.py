"""Portfolio constraint rule set."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from finschema.quality.report import Severity, ValidationIssue


def _get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _money_amount(value: Any) -> Decimal | None:
    if value is None:
        return None
    if hasattr(value, "amount"):
        return Decimal(str(value.amount))
    if isinstance(value, dict) and "amount" in value:
        return Decimal(str(value["amount"]))
    return None


def _money_currency(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "currency"):
        return str(value.currency)
    if isinstance(value, dict) and "currency" in value:
        return str(value["currency"])
    return None


def validate_portfolio(
    record: Any,
    *,
    record_index: int | None,
    config: dict[str, Any],
    context: dict[str, Any],
) -> list[ValidationIssue]:
    del context
    positions = _get(record, "positions")
    if not isinstance(positions, list):
        return []

    issues: list[ValidationIssue] = []

    base_currency_raw = _get(record, "base_currency")
    base_currency = str(base_currency_raw) if base_currency_raw is not None else None

    nav = _get(record, "nav")
    cash = _get(record, "cash")

    nav_amount = _money_amount(nav)
    cash_amount = _money_amount(cash)
    nav_currency = _money_currency(nav)
    cash_currency = _money_currency(cash)

    if nav_amount is None or cash_amount is None:
        return []

    if nav_amount <= 0:
        issues.append(
            ValidationIssue(
                rule="nav_positive",
                severity=Severity.ERROR,
                message=f"NAV must be > 0, got {nav_amount}",
                field="nav",
                record_index=record_index,
            )
        )
        return issues

    seen: set[str] = set()
    market_sum = Decimal("0")
    weight_sum = Decimal("0")
    max_single_position = Decimal(str(config.get("max_single_position", 0.25)))

    for position in positions:
        isin = _get(position, "isin")
        isin_key = str(isin) if isin is not None else ""
        if isin_key:
            if isin_key in seen:
                issues.append(
                    ValidationIssue(
                        rule="no_duplicate_positions",
                        severity=Severity.ERROR,
                        message=f"Duplicate position found for {isin_key}",
                        field="positions",
                        record_index=record_index,
                    )
                )
            seen.add(isin_key)

        market_value = _get(position, "market_value")
        market_amount = _money_amount(market_value)
        market_currency = _money_currency(market_value)
        if market_amount is not None:
            market_sum += market_amount

            if (
                base_currency is not None
                and market_currency is not None
                and market_currency != base_currency
            ):
                issues.append(
                    ValidationIssue(
                        rule="currency_consistent",
                        severity=Severity.ERROR,
                        message=(
                            f"Position currency {market_currency} does not match "
                            f"portfolio base currency {base_currency}"
                        ),
                        field="positions.market_value.currency",
                        record_index=record_index,
                    )
                )

            weight_value = _get(position, "weight")
            if weight_value is not None:
                pos_weight = Decimal(str(getattr(weight_value, "as_decimal", weight_value)))
            else:
                pos_weight = market_amount / nav_amount

            weight_sum += pos_weight
            if pos_weight > max_single_position:
                issues.append(
                    ValidationIssue(
                        rule="max_single_position",
                        severity=Severity.WARNING,
                        message=(
                            f"Position {isin_key} weight {pos_weight:.4f} exceeds "
                            f"limit {max_single_position:.4f}"
                        ),
                        field="positions.weight",
                        record_index=record_index,
                    )
                )

    if base_currency is not None and nav_currency is not None and nav_currency != base_currency:
        issues.append(
            ValidationIssue(
                rule="currency_consistent",
                severity=Severity.ERROR,
                message=f"NAV currency {nav_currency} does not match base currency {base_currency}",
                field="nav.currency",
                record_index=record_index,
            )
        )

    if base_currency is not None and cash_currency is not None and cash_currency != base_currency:
        issues.append(
            ValidationIssue(
                rule="currency_consistent",
                severity=Severity.ERROR,
                message=f"Cash currency {cash_currency} does not match base currency {base_currency}",
                field="cash.currency",
                record_index=record_index,
            )
        )

    nav_tolerance = Decimal("0.01")
    computed_nav = market_sum + cash_amount
    if abs(computed_nav - nav_amount) > nav_tolerance:
        issues.append(
            ValidationIssue(
                rule="nav_consistency",
                severity=Severity.ERROR,
                message=(f"market_sum + cash = {computed_nav} does not match NAV {nav_amount}"),
                field="nav",
                record_index=record_index,
                context={"computed_nav": str(computed_nav), "nav": str(nav_amount)},
            )
        )

    total_weight = weight_sum + (cash_amount / nav_amount)
    weight_tolerance = Decimal(str(config.get("weight_tolerance", 0.001)))
    if abs(total_weight - Decimal("1")) > weight_tolerance:
        issues.append(
            ValidationIssue(
                rule="weights_sum_to_one",
                severity=Severity.ERROR,
                message=(
                    f"Portfolio weights total {total_weight:.4f}, expected 1.0000 "
                    f"(tol {weight_tolerance:.4f})"
                ),
                field="positions.weight",
                record_index=record_index,
                context={"actual": str(total_weight), "tolerance": str(weight_tolerance)},
            )
        )

    return issues
