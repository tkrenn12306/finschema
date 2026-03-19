"""Optional ecosystem integrations."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .fastapi import FinschemaMiddleware

__all__ = [
    "FinschemaMiddleware",
    "register_pandas_accessors",
    "register_polars_namespace",
]


def __getattr__(name: str) -> Any:
    if name == "FinschemaMiddleware":
        from .fastapi import FinschemaMiddleware

        return FinschemaMiddleware
    if name == "register_pandas_accessors":
        from .pandas import register_pandas_accessors

        return register_pandas_accessors
    if name == "register_polars_namespace":
        from .polars import register_polars_namespace

        return register_polars_namespace
    raise AttributeError(f"module 'finschema.integrations' has no attribute {name!r}")
