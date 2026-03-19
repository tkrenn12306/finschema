"""Decorator helpers for custom quality rules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .report import Severity


@dataclass(frozen=True, slots=True)
class RuleMetadata:
    name: str
    severity: Severity
    description: str = ""


def rule(
    *,
    name: str,
    severity: Severity = Severity.ERROR,
    description: str = "",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def _decorate(func: Callable[..., Any]) -> Callable[..., Any]:
        func.__finschema_rule__ = RuleMetadata(name, severity, description)  # type: ignore[attr-defined]
        return func

    return _decorate


def get_rule_metadata(func: Callable[..., Any]) -> RuleMetadata | None:
    metadata = getattr(func, "__finschema_rule__", None)
    if isinstance(metadata, RuleMetadata):
        return metadata
    return None
